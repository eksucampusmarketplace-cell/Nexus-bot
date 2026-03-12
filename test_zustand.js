// Test file for verifying Zustand-like store implementation in the webapp
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  page.on('console', msg => {
    console.log('BROWSER LOG:', msg.text());
  });
  
  page.on('pageerror', error => {
    console.log('PAGE ERROR:', error.message);
  });
  
  await page.goto('http://localhost:8080/webapp/index.html');
  
  // Wait for Babel to transform and run
  await new Promise(resolve => setTimeout(resolve, 5000));
  
  // Check if React app rendered
  const rootContent = await page.evaluate(() => {
    const root = document.getElementById('root');
    return root ? root.innerHTML.substring(0, 500) : 'No root element';
  });
  
  console.log('Root content:', rootContent);
  
  await browser.close();
})();
