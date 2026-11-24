/* Run against a fresh isolated backend on the project test port.
 * ZHIJI_PW optionally locates an existing Playwright installation.
 * Pass "before" for baseline screenshots. Artifacts are written to the working directory.
 */
const assert = require('node:assert/strict')
const { chromium } = require(process.env.ZHIJI_PW || 'playwright')
const before = process.argv[2] === 'before'
const origin = 'http://127.0.0.1:18766'
async function main() {
  const browser = await chromium.launch({ channel: 'msedge' })
  try {
    const page = await browser.newPage({ timezoneId: 'Asia/Shanghai' })
    page.setDefaultTimeout(4500)
    const status = await page.request.get(origin + '/api/auth/status')
    assert.equal((await status.json()).needs_setup, true, 'Expected a fresh test database')
    await page.clock.setFixedTime(new Date('2026-02-01T00:00:01+08:00'))
    await page.goto(origin)
    await page.locator('input[type=password]').nth(0).fill('isolated-range-password')
    await page.locator('input[type=password]').nth(1).fill('isolated-range-password')
    await page.getByRole('button', {name:'设置密码并登录'}).click()
    const button = (name, parent = page) => parent.getByRole('button', {name, exact:true})
    const trigger = button('笔记日期范围')
    const panel = page.locator('[popover]:popover-open').last()
    const open = async () => { await trigger.click(); await panel.waitFor() }
    for (const [width,height] of [[1440,900],[1280,800],[768,1024],[390,844]]) {
      await page.setViewportSize({width,height})
      await open()
      if (before) await panel.locator('.date-calendar > summary').click()
      const box = await panel.boundingBox()
      if (!before) {
        assert.ok(box.x >= -1 && box.y >= -1 && box.x+box.width <= width+1 && box.y+box.height <= height+1, JSON.stringify(box))
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth), width)
      }
      await page.screenshot({path:(before?'before':'after')+'-'+width+'.png'})
      await page.keyboard.press('Escape')
      await panel.waitFor({state:'hidden'})
      if (before && width !== 390) {
        await open()
        if(await panel.locator('.date-calendar').getAttribute('open') !== null) await panel.locator('.date-calendar > summary').click()
        await page.keyboard.press('Escape')
      }
    }
    if (before) return
    await page.setViewportSize({width:1440,height:900})
    const requests=[]
    page.on('request',r=>{if(r.url().includes('/api/records/search?')) requests.push(new URL(r.url()).searchParams)})
    const day = key => panel.locator('[data-day="'+key+'"]')
    const scroll = () => page.evaluate(()=>[document.scrollingElement.scrollTop,document.querySelector('.main-area').scrollTop,document.querySelector('.library-scroll-region').scrollTop])
    const bounds = async () => {const el=await trigger.boundingBox();return [el.x,el.y]}
    const initial = await scroll(), pos=await bounds()
    await trigger.focus()
    await trigger.press('Enter')
    await page.keyboard.press('Tab')
    assert.ok(await panel.evaluate(el=>el.contains(document.activeElement)))
    await page.keyboard.press('Escape')
    for(const method of ['Escape','取消','关闭日期选择','outside']) {
      await open()
      const count = requests.length
      await day('2026-02-04').click()
      if(method === 'Escape') await page.keyboard.press('Escape')
      else if(method === 'outside') await page.locator('h1').first().click()
      else await button(method,panel).click()
      await panel.waitFor({state:'hidden'})
      assert.equal(requests.length,count)
      if(method!=='outside') assert.ok(await trigger.evaluate(el=>el===document.activeElement), method+' active='+await page.evaluate(()=>document.activeElement.outerHTML.slice(0,300))+' trigger visible='+await trigger.isVisible())
      assert.deepEqual(await scroll(),initial)
      assert.deepEqual(await bounds(),pos)
      await open()
      assert.equal(await panel.locator('.bounds [aria-pressed=true]').innerText(),'开始日期\n不限')
      await button('取消',panel).click()
    }
    await open()
    await day('2026-02-28').click()
    await day('2026-02-28').press('ArrowRight')
    await day('2026-03-01').press('Enter')
    async function commit(click,from,to) {
      const next=page.waitForRequest(r=>r.url().includes('/api/records/search?'))
      await click()
      const params=new URL((await next).url()).searchParams
      assert.equal(params.get('date_from'),from)
      assert.equal(params.get('date_to'),to)
    }
    await commit(()=>button('应用日期',panel).click(),'2026-02-28','2026-03-01')
    await open()
    await day('2026-02-28').click()
    await day('2026-02-03').click()
    assert.ok(await button('应用日期',panel).isDisabled())
    await panel.getByRole('alert').waitFor()
    await button('取消',panel).click()
    await button('置顶').first().click()
    await button('我的知识库').first().click()
    await open()
    assert.match(await panel.locator('.bounds').innerText(),/2026年2月28日/)
    await button('取消',panel).click()
    for(const [label,from,to] of [
      ['今天','2026-02-01','2026-02-01'],['最近 7 天','2026-01-26','2026-02-01'],
      ['最近 30 天','2026-01-03','2026-02-01'],['本月','2026-02-01','2026-02-28'],['不限时间',null,null]
    ]) {
      await open()
      await commit(()=>button(label,panel.locator('.presets')).click(),from,to)
    }
    await button('附件库').first().click()
    const upload=button('上传日期范围')
    await upload.click()
    await button('最近 7 天',panel).click()
    assert.match(await upload.innerText(),/2026-01-26 至 2026-02-01/)
    await button('附件回收站').click()
    await button('删除日期范围').click()
    await day('2026-02-01').click()
    await button('取消',panel).click()
    assert.doesNotMatch(await button('删除日期范围').innerText(),/2026-/)
    await button('待办事项').first().click()
    assert.ok(await page.getByLabel('待办日期范围').locator('option').count() >= 5)
    console.log('PASS ranges: dismiss x4, focus/scroll, cross-month keyboard, invalid range, saved filter, local midnight + 5 presets, attachment/trash, task periods, 4 viewports')
  } finally { await browser.close() }
}
main().catch(e=>{console.error(e);process.exitCode=1})
