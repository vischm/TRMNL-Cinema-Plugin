const { Liquid } = require('liquidjs');
const fs = require('fs');

const engine = new Liquid({
  root: './src',
  extname: '.liquid'
});

const templateFile = 'main.liquid';
const data = JSON.parse(fs.readFileSync('./samples/sample-data.json', 'utf8'));

engine.renderFile(templateFile, data).then(output => {
  fs.writeFileSync('./out/preview.html', output);
  console.log('Rendered preview output saved to out/preview.html');
});