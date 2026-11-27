const {chromium}=require(process.env.ZHIJI_PW||'playwright')
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url')
const [stage,out]=process.argv.slice(2),origin='http://127.0.0.1:8765'
assert.ok(['before','after','refresh'].includes(stage),'Unknown comparison stage')
assert.ok(process.env.ZHIJI_TEST_PASSWORD,'Set the isolated preview password')
async function run(){
 const browser=await chromium.launch({channel:'msedge'})
 try{
 const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:2}),metrics=[],errors=[]
 page.on('pageerror',e=>errors.push(e.message))
 page.setDefaultTimeout(5000)
 const file=pathToFileURL(path.join(out,'R3','index.html')).href
 await page.goto(file)
 const rows=await page.evaluate(()=>notes.slice(0,25).map((n,i)=>({title:n[0],content:noteBody(i),category:n[1],note_date:dateOf(i)})))
 const post=(route,data)=>page.request.post(origin+route,{headers:{Origin:origin},data})
 const button=n=>page.getByRole('button',{name:n,exact:true}).first()
 const marker=await page.request.get(origin+'/assets/zh004a-isolated-test.txt')
 assert.equal((await marker.text()).trim(),'zh004a-disposable-fixtures','Expected an explicitly marked disposable test server')
 const status=await (await page.request.get(origin+'/api/auth/status')).json()
 const auth=await post('/api/auth/'+(status.needs_setup?'setup':'login'),{password:process.env.ZHIJI_TEST_PASSWORD})
 assert.ok(auth.ok(),await auth.text())
 if(status.needs_setup)for(const data of [...rows].reverse()){
  const create=await post('/api/records',data);assert.ok(create.ok(),await create.text())
 }
 const dir=path.join(out,'screenshots');fs.mkdirSync(dir,{recursive:true})
 for(const version of stage==='before'?['r3','before']:['after']){
  for(const [width,height] of [[1440,900],[1280,800],[768,1024],[390,844]]){
   await page.setViewportSize({width,height})
   if(version==='r3'){await page.goto(file);await page.evaluate(()=>openNoteByTitle('周五交付新版首页'))}
   else{await page.goto(origin);const heading=page.locator('.note-detail-title').filter({hasText:rows[0].title})
    await page.waitForTimeout(300);if(!(await heading.isVisible()))await button(rows[0].title).click();await heading.waitFor()}
   await page.waitForTimeout(200);await page.screenshot({path:path.join(dir,version+'-'+width+'.png')})
   metrics.push(await page.evaluate(({version,width})=>{const w=s=>Math.round(document.querySelector(s)?.getBoundingClientRect().width||0);return {version,width,overflow:document.documentElement.scrollWidth-innerWidth,nav:w('.sidebar'),list:w('.list-panel,.library-scroll-region'),text:w('.reader-body p,.writing-preview p'),title:document.querySelector('.reader-body h2,.note-detail-title')?.textContent}}, {version,width}))
  }
 }
 fs.writeFileSync(path.join(dir,(stage==='refresh'?'after':stage)+'.json'),JSON.stringify({metrics,errors},null,2));assert.deepEqual(errors,[])
 if(stage==='after'){
  await page.setViewportSize({width:1440,height:900});await page.goto(origin)
  const divider=page.getByRole('separator',{name:'调整笔记列表宽度'})
  await divider.waitFor()
  const w=await page.locator('.library-scroll-region').evaluate(el=>el.clientWidth)
  await divider.press('ArrowRight')
  assert.ok(await page.locator('.library-scroll-region').evaluate(el=>el.clientWidth)>w)
  await divider.press('ArrowLeft')
  const name='隔离操作验收 '+Date.now();await button('新建笔记').click();await page.getByLabel('记录标题').fill(name)
  await page.locator('.capture-form .formatted-editor').fill('新建正文')
  await button('保存记录').click();await button(name).first().click();await page.locator('.note-edit-action').click()
  await page.locator('.edit-form .formatted-editor').click();await page.keyboard.press('Control+a');await page.keyboard.insertText('修改正文通过');await button('保存修改').click()
  await page.locator('.writing-preview').filter({hasText:'修改正文通过'}).first().waitFor()
  for(const n of ['置顶','收集箱','我的知识库'])await button(n).click()
  const r=(await (await page.request.get(origin+'/api/records/search?q='+encodeURIComponent(name))).json()).records[0]
  assert.equal(r.content,'修改正文通过')
  assert.ok((await page.request.delete(origin+'/api/records/'+r.id,{headers:{Origin:origin}})).ok())
 }
 console.log('PASS '+stage,metrics)
 }finally{await browser.close()}
}
run().catch(e=>{console.error(e);process.exitCode=1})
