const https = require('https');

exports.handler = async function(event) {
  const BDL_KEY = '9a6f6a65-660c-4774-96ff-2485b91b6d20';
  const FOOTBALL_KEY = 'db65666859e94711b095731f01b71157';
  const path = event.queryStringParameters?.path || '';
  const source = event.queryStringParameters?.source || 'bdl';

  if (!path) {
    return { statusCode: 400, body: JSON.stringify({ error: 'path manquant' }) };
  }

  let hostname, headers;
  if (source === 'football') {
    hostname = 'api.football-data.org';
    headers = { 'X-Auth-Token': FOOTBALL_KEY };
  } else if (source === 'espn') {
    hostname = 'site.api.espn.com';
    headers = { 'User-Agent': 'Mozilla/5.0' };
  } else {
    // BallDontLie par défaut
    hostname = 'api.balldontlie.io';
    headers = { 'Authorization': BDL_KEY };
  }

  return new Promise((resolve) => {
    const req = https.request({
      hostname,
      path,
      method: 'GET',
      headers
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
