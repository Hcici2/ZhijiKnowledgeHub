const {chromium}=require(process.env.ZHIJI_PW || 'playwright')
const {execFileSync}=require('node:child_process')
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict')
const {pathToFileURL}=require('node:url')
const output=path.join(__dirname,'evidence-r3')
const scenes={list:'默认知识库',reader:'长文阅读',calendar:'完整月历',clip:'附件网格',files:'附件列表',detail:'附件详情',check:'任务属性列',settings:'设置',compose:'文档编辑',date:'日期弹层',link:'网站收藏',trash:'回收站',inbox:'收集箱',star:'置顶'}
async function run(){
 const browser=await chromium.launch({channel:'msedge'})
 try{
 const baseline=fs.mkdtempSync(path.join(os.tmpdir(),'zh-r2-base-'))
 const tracked=execFileSync('git',['ls-tree','-r','--name-only','709ecbd','design/zh-ui-003'],{cwd:path.resolve(__dirname,'../..'),encoding:'utf8'}).trim().split(/\r?\n/)
 for(const rel of tracked.filter(p=>!/\/evidence|\/verify|\/compare/.test(p))){
  const target=path.join(baseline,rel.slice('design/zh-ui-003/'.length))
  fs.mkdirSync(path.dirname(target),{recursive:true})
  fs.writeFileSync(target,execFileSync('git',['show','709ecbd:'+rel],{cwd:path.resolve(__dirname,'../..'),maxBuffer:16000000}))
 }
 const probe=await browser.newPage()
 await probe.goto(pathToFileURL(path.join(__dirname,'index.html')).href)
 const sample=await probe.evaluate(()=>({notes:notes.map(n=>[...n]),extras:R2Extras.samples()}))
 await probe.close()
 const extraFile=path.join(baseline,'extras.js')
 const original=fs.readFileSync(extraFile,'utf8')
 assert.ok(original.includes('return {render,bind,samples:'))
 fs.writeFileSync(extraFile,original.replace('return {render,bind,samples:',()=> 'files.splice(0,files.length,...'+JSON.stringify(sample.extras.files)+');tasks.splice(0,tasks.length,...'+JSON.stringify(sample.extras.tasks)+');return {render,bind,samples:'))
 const metrics=[],errors=[]
 for(const version of ['R2','R3']){
  const ctx=await browser.newContext({deviceScaleFactor:2,timezoneId:'Asia/Shanghai'})
  const page=await ctx.newPage()
  page.setDefaultTimeout(2500)
  page.on('dialog',d=>d.accept())
  page.on('pageerror',e=>errors.push(String(e)))
  await page.clock.setFixedTime(new Date('2026-11-18T10:00:00+08:00'))
  await page.goto(pathToFileURL(path.join(version==='R2'?baseline:__dirname,'index.html')).href)
  if(version==='R2')await page.evaluate(s=>notes.splice(0,notes.length,...s.notes),sample)
  const dir=path.join(output,version);fs.mkdirSync(dir,{recursive:true})
  for(const [width,height] of [[1440,900],[1280,800],[768,1024],[390,844]]){
   await page.setViewportSize({width,height})
   for(const id of Object.keys(scenes)){
    await page.evaluate(id=>go(id==='list'?'reader':['detail','files'].includes(id)?'clip':id),id)
    if(id==='reader')await page.evaluate(()=>openNoteByTitle(notes[0][0]))
    if(id==='files'||id==='clip'||id==='detail'){
     const toggle=page.locator('[data-x=layout]')
     const isList=(await toggle.innerText()).includes('网格')
     if(isList!==(id==='files'))await toggle.click()
     if(id==='detail')await page.locator('[data-file="3"]').first().click()
     else if(await page.locator('[data-x=dismiss]').count())await page.locator('[data-x=dismiss]').click()
    }
    if(id==='compose'){await page.locator('[name=title]').fill('阅读与记录的边界');await page.locator('[name=body]').fill('每次重读时，先写下自己想回答的问题。\n\n再用原文中的例子检验理解，最后标出下一次要追问的线索。')}
    if(id==='date' && width<850 && !(await page.locator(':popover-open').count())){
      const t=page.locator('.range-trigger:visible');if(await t.count())await t.first().click()
    }
    await page.waitForTimeout(70)
    const m=await page.evaluate(()=>{const rect=s=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}}
     return {overflow:document.documentElement.scrollWidth-innerWidth,body:rect('.reader-body'),title:rect('.reader-bar>span'),close:rect('[data-cmd=close]'),panel:rect(':popover-open'),taskCount:document.querySelectorAll('.ex-task').length,fileCount:document.querySelectorAll('[data-file]').length}})
    metrics.push({version,width,id,...m})
    if(width===1440||width===390&&['reader','compose','date','check'].includes(id))await page.screenshot({path:path.join(dir,id+'-'+width+'.png'),animations:'disabled'})
   }
  }
  await ctx.close()
 }
 fs.writeFileSync(path.join(output,'measurements.json'),JSON.stringify({metrics,errors},null,2))
 const items=Object.entries(scenes).map(([id,label])=>'<h2>'+label+'</h2><section>'+['R2','R3'].map(v=>'<figure><figcaption>'+v+'</figcaption><a href="'+v+'/'+id+'-1440.png"><img loading="lazy" src="'+v+'/'+id+'-1440.png"></a></figure>').join('')+'</section>').join('')
 const mobile=['reader','compose','date','check'].map(id=>'<h2>390px · '+scenes[id]+'</h2><section>'+['R2','R3'].map(v=>'<figure><figcaption>'+v+'</figcaption><img loading="lazy" src="'+v+'/'+id+'-390.png"></figure>').join('')+'</section>').join('')
 fs.writeFileSync(path.join(output,'index.html'),'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>R2 与 R3 · 同尺寸对照</title><style>body{font:15px/1.6 system-ui;padding:2vw;color:#27322d}section{display:grid;grid-template-columns:1fr 1fr;gap:12px}figure{margin:0}img{max-width:100%;border:1px solid #ddd}</style><h1>知己 · 第三轮精修</h1><p>左为 R2，右为 R3。桌面 1440×900，移动 390×844，设备像素比均为 2。两版载入同一份笔记、文件和任务示例。功能差异保留。</p>'+items+mobile)
 console.log(JSON.stringify({metrics:metrics.length,errors,overflow:metrics.filter(x=>x.overflow>0).map(x=>[x.version,x.width,x.id]),files:sample.extras.files.length,mobile:metrics.filter(x=>x.width===390&&x.id==='reader')},null,2))
 assert.deepEqual(errors,[])
 }finally{await browser.close()}
}
run().catch(e=>{console.error(e);process.exitCode=1})
