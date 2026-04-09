const https = require('https');

exports.handler = async function(event) {
  const API_KEY = 'db65666859e94711b095731f01b71157';
  const path = event.queryStringParameters?.path || '';

  if (!path) {
    return { statusCode: 400, body: JSON.stringify({ error: 'path manquant' }) };
  }

  return new Promise((resolve) => {
    const req = https.request({
      hostname: 'api.football-data.org',
      path: path,
      method: 'GET',
      headers: { 'X-Auth-Token': API_KEY }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({
        statusCode: 200,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        },
        body: data
      }));
    });
    req.on('error', err => resolve({
      statusCode: 500,
      body: JSON.stringify({ error: err.message })
    }));
    req.end();
  });
};
