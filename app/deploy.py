"""Despliegue reproducible en la cuenta del participante y con permisos acotados."""
import hashlib
import json
import mimetypes
import os
import sys
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from aws_config import crear_sesion, nombre_stack, validar_preparacion, REGION

ROOT = Path(__file__).resolve().parent
validar_preparacion(ROOT)
STACK = nombre_stack()
FUNCTION = STACK + "-api"
sesion = crear_sesion()
s3, cfn = sesion.client("s3"), sesion.client("cloudformation")
cuenta = sesion.client("sts").get_caller_identity()["Account"]
bucket = f"{STACK}-{cuenta}-{REGION}"
print("Perfil seleccionado:", sesion.profile_name, "Cuenta de destino:", cuenta, "Región:", REGION, "Stack:", STACK, flush=True)
try:
    s3.head_bucket(Bucket=bucket)
except ClientError as error:
    if error.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
        raise
    s3.create_bucket(Bucket=bucket)
    s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration={"BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    s3.put_bucket_encryption(Bucket=bucket, ServerSideEncryptionConfiguration={"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]})
    s3.put_bucket_tagging(Bucket=bucket, Tagging={"TagSet": [{"Key": "Project", "Value": STACK}]})
s3.put_bucket_lifecycle_configuration(Bucket=bucket, LifecycleConfiguration={"Rules": [{"ID": "temporary-upload-expiry", "Status": "Enabled", "Filter": {"Prefix": "uploads/"}, "Expiration": {"Days": 1}, "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1}}, {"ID": "imported-data-expiry", "Status": "Enabled", "Filter": {"Prefix": "imported/"}, "Expiration": {"Days": 1}}]})

paquete = ROOT / ".build/lambda.zip"
with zipfile.ZipFile(paquete, "w", zipfile.ZIP_DEFLATED) as zip_lambda:
    for ruta in (ROOT / ".build/package").rglob("*"):
        if ruta.is_file() and "__pycache__" not in ruta.parts and not ruta.name.endswith(".pyc"):
            zip_lambda.write(ruta, ruta.relative_to(ROOT / ".build/package").as_posix())
    for ruta in (ROOT / "backend").glob("*.py"):
        zip_lambda.write(ruta, ruta.name)
digest = hashlib.sha256(paquete.read_bytes()).hexdigest()[:16]
clave_codigo = f"artifacts/lambda-{digest}.zip"
s3.upload_file(str(paquete), bucket, clave_codigo)
print("Paquete Lambda preparado:", paquete.stat().st_size, "bytes", flush=True)
for ruta in (ROOT / "data").rglob("*"):
    if ruta.is_file():
        tipo = "application/json" if ruta.suffix == ".json" else "application/octet-stream"
        clave = "datasets/" + ruta.relative_to(ROOT / "data").as_posix()
        try:
            existente = s3.head_object(Bucket=bucket, Key=clave)
        except ClientError:
            existente = {}
        if existente.get("ContentLength") != ruta.stat().st_size:
            s3.upload_file(str(ruta), bucket, clave, ExtraArgs={"ContentType": tipo})
print("Series públicas subidas al bucket privado.", flush=True)
for ruta in (ROOT / "frontend").rglob("*"):
    if ruta.is_file():
        tipo = {".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".ipynb": "application/x-ipynb+json"}.get(ruta.suffix) or mimetypes.guess_type(ruta.name)[0] or "application/octet-stream"
        s3.upload_file(str(ruta), bucket, "site/" + ruta.relative_to(ROOT / "frontend").as_posix(), ExtraArgs={"ContentType": tipo, "CacheControl": "max-age=300"})

ref = lambda name: {"Ref": name}
att = lambda resource, attr: {"Fn::GetAtt": [resource, attr]}
sub = lambda text: {"Fn::Sub": text}
origen = {"Id": "api", "DomainName": {"Fn::Select": [2, {"Fn::Split": ["/", att("ApiUrl", "FunctionUrl")]}]}, "OriginAccessControlId": ref("ApiOac"), "CustomOriginConfig": {"HTTPSPort": 443, "OriginProtocolPolicy": "https-only", "OriginSSLProtocols": ["TLSv1.2"], "OriginReadTimeout": 60}}
plantilla = {
 "AWSTemplateFormatVersion": "2010-09-09", "Description": "SIPAIM educational DICOM viewer, Amazon Bedrock and Polly. CPU-only; no clinical diagnosis.",
 "Resources": {
  "ApiRole": {"Type": "AWS::IAM::Role", "Properties": {"AssumeRolePolicyDocument": {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]}, "Policies": [{"PolicyName": "EducationalImaging", "PolicyDocument": {"Version": "2012-10-17", "Statement": [
   {"Effect": "Allow", "Action": ["logs:CreateLogStream", "logs:PutLogEvents"], "Resource": f"arn:aws:logs:{REGION}:{cuenta}:log-group:/aws/lambda/{FUNCTION}:*"},
   {"Effect": "Allow", "Action": "s3:GetObject", "Resource": f"arn:aws:s3:::{bucket}/datasets/*"},
   {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], "Resource": [f"arn:aws:s3:::{bucket}/uploads/*", f"arn:aws:s3:::{bucket}/imported/*"]},
   {"Effect": "Allow", "Action": "bedrock:InvokeModel", "Resource": f"arn:aws:bedrock:{REGION}::foundation-model/amazon.nova-lite-v1:0"},
   {"Effect": "Allow", "Action": "polly:SynthesizeSpeech", "Resource": "*"}
  ]}}]}},
  "ApiLogs": {"Type": "AWS::Logs::LogGroup", "Properties": {"LogGroupName": f"/aws/lambda/{FUNCTION}", "RetentionInDays": 7}},
  "Api": {"Type": "AWS::Lambda::Function", "DependsOn": "ApiLogs", "Properties": {"FunctionName": FUNCTION, "Runtime": "python3.12", "Handler": "handler.handler", "Architectures": ["x86_64"], "Role": att("ApiRole", "Arn"), "MemorySize": 2048, "Timeout": 90, "ReservedConcurrentExecutions": 3, "Code": {"S3Bucket": bucket, "S3Key": clave_codigo}, "Environment": {"Variables": {"DATA_BUCKET": bucket, "BEDROCK_MODEL": "amazon.nova-lite-v1:0"}}, "Tags": [{"Key": "Project", "Value": STACK}]}},
  "ApiUrl": {"Type": "AWS::Lambda::Url", "Properties": {"TargetFunctionArn": ref("Api"), "AuthType": "AWS_IAM", "InvokeMode": "BUFFERED"}},
  "ApiOac": {"Type": "AWS::CloudFront::OriginAccessControl", "Properties": {"OriginAccessControlConfig": {"Name": STACK + "-api", "OriginAccessControlOriginType": "lambda", "SigningBehavior": "always", "SigningProtocol": "sigv4"}}},
  "SiteOac": {"Type": "AWS::CloudFront::OriginAccessControl", "Properties": {"OriginAccessControlConfig": {"Name": STACK + "-site", "OriginAccessControlOriginType": "s3", "SigningBehavior": "always", "SigningProtocol": "sigv4"}}},
  "ApiCache": {"Type": "AWS::CloudFront::CachePolicy", "Properties": {"CachePolicyConfig": {"Name": STACK + "-no-cache", "DefaultTTL": 0, "MaxTTL": 0, "MinTTL": 0, "ParametersInCacheKeyAndForwardedToOrigin": {"EnableAcceptEncodingGzip": False, "EnableAcceptEncodingBrotli": False, "CookiesConfig": {"CookieBehavior": "none"}, "HeadersConfig": {"HeaderBehavior": "none"}, "QueryStringsConfig": {"QueryStringBehavior": "none"}}}}},
  "ApiForward": {"Type": "AWS::CloudFront::OriginRequestPolicy", "Properties": {"OriginRequestPolicyConfig": {"Name": STACK + "-api-headers", "CookiesConfig": {"CookieBehavior": "none"}, "HeadersConfig": {"HeaderBehavior": "allExcept", "Headers": ["host"]}, "QueryStringsConfig": {"QueryStringBehavior": "all"}}}},
  "Distribution": {"Type": "AWS::CloudFront::Distribution", "Properties": {"DistributionConfig": {"Enabled": True, "Comment": "SIPAIM 2026 DICOM Lab educational demo", "DefaultRootObject": "index.html", "PriceClass": "PriceClass_100", "HttpVersion": "http2and3", "IPV6Enabled": True, "ViewerCertificate": {"CloudFrontDefaultCertificate": True}, "Origins": [origen, {"Id": "site", "DomainName": f"{bucket}.s3.{REGION}.amazonaws.com", "OriginPath": "/site", "S3OriginConfig": {"OriginAccessIdentity": ""}, "OriginAccessControlId": ref("SiteOac")}], "DefaultCacheBehavior": {"TargetOriginId": "site", "ViewerProtocolPolicy": "redirect-to-https", "AllowedMethods": ["GET", "HEAD", "OPTIONS"], "CachedMethods": ["GET", "HEAD"], "Compress": True, "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6", "ResponseHeadersPolicyId": "67f7725c-6f97-4210-82d7-5512b31e9d03"}, "CacheBehaviors": [{"PathPattern": "/api/*", "TargetOriginId": "api", "ViewerProtocolPolicy": "https-only", "AllowedMethods": ["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"], "CachedMethods": ["GET", "HEAD"], "Compress": True, "CachePolicyId": ref("ApiCache"), "OriginRequestPolicyId": ref("ApiForward")}], "CustomErrorResponses": [{"ErrorCode": 403, "ErrorCachingMinTTL": 0}, {"ErrorCode": 500, "ErrorCachingMinTTL": 0}, {"ErrorCode": 503, "ErrorCachingMinTTL": 0}]}}},
  "SitePolicy": {"Type": "AWS::S3::BucketPolicy", "Properties": {"Bucket": bucket, "PolicyDocument": {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "cloudfront.amazonaws.com"}, "Action": "s3:GetObject", "Resource": f"arn:aws:s3:::{bucket}/site/*", "Condition": {"StringEquals": {"AWS:SourceArn": sub("arn:aws:cloudfront::${AWS::AccountId}:distribution/${Distribution}")}}}]}}},
  "ApiUrlPermission": {"Type": "AWS::Lambda::Permission", "Properties": {"FunctionName": ref("Api"), "Action": "lambda:InvokeFunctionUrl", "Principal": "cloudfront.amazonaws.com", "SourceArn": sub("arn:aws:cloudfront::${AWS::AccountId}:distribution/${Distribution}"), "FunctionUrlAuthType": "AWS_IAM"}},
  "ApiInvokePermission": {"Type": "AWS::Lambda::Permission", "Properties": {"FunctionName": ref("Api"), "Action": "lambda:InvokeFunction", "Principal": "cloudfront.amazonaws.com", "SourceArn": sub("arn:aws:cloudfront::${AWS::AccountId}:distribution/${Distribution}")}}
 },
 "Outputs": {"Url": {"Value": sub("https://${Distribution.DomainName}")}, "DistributionId": {"Value": ref("Distribution")}, "FunctionName": {"Value": ref("Api")}, "Bucket": {"Value": bucket}, "FunctionUrl": {"Value": att("ApiUrl", "FunctionUrl")}}
}
(ROOT / "cloudformation.json").write_text(json.dumps(plantilla, indent=2), encoding="utf-8")
parametros = {"StackName": STACK, "TemplateBody": json.dumps(plantilla), "Capabilities": ["CAPABILITY_IAM"], "Tags": [{"Key": "Project", "Value": STACK}]}
try:
    anterior = cfn.describe_stacks(StackName=STACK)["Stacks"][0]
    if anterior["StackStatus"] == "ROLLBACK_COMPLETE":
        cfn.delete_stack(StackName=STACK)
        cfn.get_waiter("stack_delete_complete").wait(StackName=STACK, WaiterConfig={"Delay": 5, "MaxAttempts": 60})
        cfn.create_stack(**parametros)
        print("Infraestructura recreada tras corregir el intento fallido.", flush=True)
        anterior = None
    try:
        if anterior is not None:
            cfn.update_stack(**parametros)
            print("Actualización iniciada.", flush=True)
    except ClientError as error:
        if "No updates are to be performed" not in str(error):
            raise
        print("Infraestructura sin cambios.", flush=True)
except ClientError as error:
    if "does not exist" not in str(error):
        raise
    cfn.create_stack(**parametros)
    print("Creación de infraestructura iniciada.", flush=True)
while True:
    stack = cfn.describe_stacks(StackName=STACK)["Stacks"][0]
    estado = stack["StackStatus"]
    print("CloudFormation:", estado, flush=True)
    if not estado.endswith("IN_PROGRESS"):
        break
    time.sleep(15)
if estado not in ("CREATE_COMPLETE", "UPDATE_COMPLETE"):
    eventos = cfn.describe_stack_events(StackName=STACK)["StackEvents"]
    for evento in eventos:
        if evento["ResourceStatus"].endswith("FAILED"):
            print(evento["LogicalResourceId"], evento.get("ResourceStatusReason"), flush=True)
    raise SystemExit("El despliegue no se completó.")
outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}
outputs.update({"StackName": STACK, "Region": REGION})
(ROOT / "deployment.json").write_text(json.dumps(outputs, indent=2), encoding="utf-8")
s3.put_bucket_cors(Bucket=bucket, CORSConfiguration={"CORSRules": [{"AllowedOrigins": [outputs["Url"]], "AllowedMethods": ["POST"], "AllowedHeaders": ["*"], "MaxAgeSeconds": 600}]})
sesion.client("cloudfront").create_invalidation(DistributionId=outputs["DistributionId"], InvalidationBatch={"Paths": {"Quantity": 1, "Items": ["/*"]}, "CallerReference": str(time.time_ns())})
print("Aplicación desplegada:", outputs["Url"], flush=True)
print("Acceso directo habilitado; no se requiere código en la aplicación.", flush=True)
