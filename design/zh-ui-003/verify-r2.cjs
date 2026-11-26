const {chromium}=require(process.env.ZHIJI_PW || 'playwright')
const fs=require('node:fs'), path=require('node:path')
const {pathToFileURL}=require('node:url')
const output=path.join(__dirname,'evidence-r2')
const baseline=process.argv[2]
if(!baseline) throw Error('Pass the directory containing the extracted a4436c1 index.html')
const scenes=['list','reader','calendar','clip','check','settings','compose','date','inbox','star','link','trash']
const sizes=[[1440,900],[1280,800],[768,1024],[390,844]]
const metrics=[]
async function capture(){
  const browser=await chromium.launch({channel:'msedge'})
  try{
    const ctx=await browser.newContext({deviceScaleFactor:2,timezoneId:'Asia/Shanghai'})
    const page=await ctx.newPage()
    await page.clock.setFixedTime(new Date('2026-11-18T10:00:00+08:00'))
    page.on('dialog',dialog=>dialog.accept())
    const warnings=[]
    page.on('pageerror',e=>warnings.push(e.message))
    for(const version of ['R2','R1']){
      const dir=path.join(output,version)
      fs.mkdirSync(dir,{recursive:true})
      await page.goto(pathToFileURL(path.resolve(version==='R1'?baseline:__dirname,'index.html')).href)
      if(version==='R2'){
        await page.waitForFunction(()=>typeof go==='function' && document.querySelector('main'))
        global.samples=await page.evaluate(()=>({notes:typeof notes==='undefined'?[]:JSON.parse(JSON.stringify(notes)),article:typeof noteBody==="function"?noteBody(0):"",extras:window.R2Extras?.samples?.()}))
      }else await page.evaluate(s=>{
        if(s.notes?.length && Array.isArray(s.notes[0])) notes.splice(0,notes.length,...s.notes)
        if(s.extras?.files?.length) files.splice(0,files.length,...s.extras.files.map(f=>f.name))
        if(s.extras?.tasks?.length) { finished=new Set(s.extras.tasks.filter(t=>t.done).map(t=>t.id)); tasks.splice(0,tasks.length,...s.extras.tasks.map(t=>t.title)) }
      },global.samples)
      for(const [width,height] of version==='R1'?sizes.slice(0,2):sizes){
        await page.setViewportSize({width,height})
        for(const scene of scenes){
          await page.evaluate(scene=>go(scene),scene)
          if(version==='R1' && scene==='reader' && global.samples.article){
            await page.locator('.reader-body .lead').evaluate((el,text)=>{el.textContent=text},global.samples.article)
          }
          if(scene==='compose'){
            const title=page.locator('input[name=title],input[aria-label*=标题],input[placeholder*=标题]').first()
            const body=page.locator('textarea,[contenteditable=true],[contenteditable=plaintext-only]').first()
            if(await title.count()) await title.fill('阅读与记录的边界')
            if(await body.count()) await body.fill('每次重读时，先写下自己想回答的问题。再用原文中的例子检验理解，最后标出下一次要追问的线索。')
          }
          await page.waitForTimeout(70)
          const metric=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth-innerWidth,
            visibleText:document.body.innerText.trim().length,heading:document.querySelector('main h1,main h2')?.textContent,
            nav:Math.round(document.querySelector('aside')?.getBoundingClientRect().width||0)}))
          metrics.push({version,width,scene,...metric})
          if(width>=1280||['reader','calendar','check','clip'].includes(scene))
            await page.screenshot({path:path.join(dir,scene+'-'+width+'.png'),animations:'disabled'})
        }
      }
    }
    fs.writeFileSync(path.join(output,'measurements.json'),JSON.stringify({metrics,warnings},null,2))
    console.log(JSON.stringify({count:metrics.length,warnings,overflow:metrics.filter(m=>m.overflow>0)}))
  }finally{await browser.close()}
}
capture().catch(e=>{console.error(e);process.exitCode=1})
