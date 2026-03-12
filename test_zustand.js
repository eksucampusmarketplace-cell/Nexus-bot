
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on('console', msg => console.log('BROWSER LOG:', msg.text()));
  await page.goto('file:///home/engine/project/webapp/index.html');
  // Wait a bit for Babel to transform and run
  await new Promise(resolve => setTimeout(resolve, 5000));
  const zustandDefined = await page.evaluate(() => typeof zustand !== 'undefined');
  const ZustandDefined = await page.evaluate(() => typeof Zustand !== 'undefined');
  console.log('zustand defined:', zustandDefined);
  console.log('Zustand defined:', ZustandDefined);
  if (zustandDefined) {
    console.log('zustand keys:', await page.evaluate(() => Object.keys(zustand)));
  }
  if (ZustandDefined) {
    console.log('Zustand keys:', await page.evaluate(() => Object.keys(Zustand)));
  }
  await browser.close();
})();
