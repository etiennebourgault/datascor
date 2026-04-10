const https = require('https');

exports.handler = async function(event) {
  const BDL_KEY      = '9a6f6a65-660c-4774-96ff-2485b91b6d20';
  const FOOTBALL_KEY = 'db65666859e94711b095731f01b71157';
  const ODDS_KEY     = 'ccdc83d94276308ac53bf341cbd6f3ce';
  const source = event.queryStringParameters?.source || 'football';
  const path   = event.queryStringParameters?.path   || '';

  if (!path) return { statusCode: 400, body: JSON.stringify({ error: 'path manquant' }) };

  let hostname, headers;
  switch(source) {
    case 'bdl':
      hostname = 'api.balldontlie.io';
      headers  = { 'Authorization': BDL_KEY };
      break;
    case 'espn':
      hostname = 'site.api.espn.com';
      headers  = { 'User-Agent': 'Mozilla/5.0' };
      break;
    case 'odds':
      hostname = 'api.the-odds-api.com';
      headers  = { 'User-Agent': 'DataScore/1.0' };
      break;
    default: // football
      hostname = 'api.football-data.org';
      headers  = { 'X-Auth-Token': FOOTBALL_KEY };
  }

  const finalPath = source === 'odds'
    ? path + (path.includes('?') ? '&' : '?') + 'apiKey=' + ODDS_KEY
    : path;

  return new Promise((resolve) => {
    const req = https.request({ hostname, path: finalPath, method: 'GET', headers }, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => resolve({
        statusCode: 200,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
        body: data
      }));
    });
    req.on('error', err => resolve({ statusCode: 500, body: JSON.stringify({ error: err.message }) }));
    req.end();
  });
};
