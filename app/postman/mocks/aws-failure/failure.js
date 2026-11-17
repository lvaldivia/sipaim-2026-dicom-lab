// Fallos HTTP de los contratos AWS, sin datos reales ni credenciales.
const http = require('http');
http.createServer((req, res) => {
  req.resume();
  if (req.method === 'POST' && req.url.includes('/model/') && req.url.endsWith('/converse')) {
    res.writeHead(429, {'Content-Type':'application/json', 'x-amzn-errortype':'ThrottlingException'});
    res.end(JSON.stringify({message:'Simulated request throttling.'}));
  } else if (req.method === 'POST' && req.url === '/v1/speech') {
    res.writeHead(503, {'Content-Type':'application/json', 'x-amzn-errortype':'ServiceFailureException'});
    res.end(JSON.stringify({message:'Simulated speech service failure.'}));
  } else {
    res.writeHead(501, {'Content-Type':'application/json'});
    res.end(JSON.stringify({message:'Endpoint not modeled by this failure simulation.'}));
  }
}).listen(process.env.PORT || 8097);
