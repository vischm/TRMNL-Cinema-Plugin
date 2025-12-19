const { Liquid } = require('liquidjs');
const fs = require('fs');

const engine = new Liquid({
  root: './src',
  extname: '.liquid'
});

const templateFile = 'main.liquid';
const data = JSON.parse(fs.readFileSync('./samples/sample-data.json', 'utf8'));

engine.renderFile(templateFile, data).then(output => {
  fs.writeFileSync('./output/result.html', output);
  console.log('Rendered output saved to output/result.html');
});