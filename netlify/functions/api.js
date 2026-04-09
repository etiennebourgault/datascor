const https = require('https');

exports.handler = async function(event) {
  const API_KEY = '431a39ff83b864a5c5579e744cd289d2';
  const path = event.queryStringParameters?.path || '';
  
  if (!path) {
    return { statusCode: 400, body: JSON.stringify({ error: 'ParamÃ¨tre path manquant' }) };
  }

  const url = `https://v3.football.api-sports.io${path}`;

  return new Promise((resolve) => {
    const options = {
      hostname: 'v3.football.api-sports.io',
      path: path,
      method: 'GET',
      headers: {
        'x-rapidapi-key': API_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        resolve({
          statusCode: 200,
          headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
          },
          body: data
        });
      });
    });

    req.on('error', (err) => {
      resolve({
        statusCode: 500,
        body: JSON.stringify({ error: err.message })
      });
    });

    req.end();
  });
};
