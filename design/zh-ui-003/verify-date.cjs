/* From the prototype directory with its static preview running. */
const { chromium } = require(process.env.ZHIJI_PW || 'playwright')
const assert = require('node:assert/strict')

async function run() {
  const browser = await chromium.launch({ channel: 'msedge' })
  try {
    const page = await browser.newPage({ timezoneId: 'Asia/Shanghai' })
    await page.clock.setFixedTime(new Date('2026-11-18T00:00:01+08:00'))
    await page.route('**/range-test.html', route => route.fulfill({
      contentType: 'text/html; charset=utf-8',
      body: '<meta charset=utf-8><meta name=viewport content="width=device-width, initial-scale=1"><link rel=stylesheet href="workspace.css"><link rel=stylesheet href="date-control.css"><span data-range-control data-from="2026-11-02" data-to="2026-11-15"></span><output></output><script src="date-control.js"></script><script>ZhRange.mountAll();document.addEventListener("rangechange",e=>document.querySelector("output").textContent=JSON.stringify(e.detail))</script>'
    }))
    await page.goto('http://127.0.0.1:18403/range-test.html')
    const trigger = page.locator('.range-trigger')
    const panel = page.locator('.range-panel:popover-open')
    for (const [width,height] of [[1440,900],[1280,800],[768,1024],[390,844]]) {
      await page.setViewportSize({ width,height })
      await trigger.click()
      const rect = await panel.boundingBox()
      assert.ok(rect.x >= -1 && rect.y >= -1 && rect.x + rect.width <= width+1 && rect.y+rect.height <= height+1,JSON.stringify(rect))
      await panel.locator('[data-day="2026-11-05"]').click()
      await page.keyboard.press('Escape')
      await panel.waitFor({state:'hidden'})
      assert.equal(await page.locator('output').textContent(),'')
      assert.ok(await trigger.evaluate(el=>el===document.activeElement))
    }
    await trigger.click()
    assert.match(await panel.locator('.bounds').innerText(),/2026年11月2日/)
    await panel.getByRole('button',{name:'最近 7 天',exact:true}).click()
    assert.deepEqual(JSON.parse(await page.locator('output').textContent()),{from:'2026-11-12',to:'2026-11-18'})
    console.log('PASS: shared date component, four viewports, cancel, focus and local preset.')
  } finally { await browser.close() }
}
run().catch(error=>{console.error(error);process.exitCode=1})

