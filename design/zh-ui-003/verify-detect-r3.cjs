const {chromium}=require(process.env.ZHIJI_PW||'playwright')
const {execFile}=require('node:child_process')
const {promisify}=require('node:util')
const fs=require('node:fs'),path=require('node:path')
const invoke=promisify(execFile)
async function run(){
 const port=19793
 const probe=await fetch('http://127.0.0.1:'+port+'/json/version').then(()=>true).catch(()=>false)
 if(probe)throw Error('Diagnostic port occupied')
 const b=await chromium.launch({channel:'msedge',args:['--remote-debugging-port='+port,'--remote-debugging-address=127.0.0.1']})
 const cases=['reader','list','inbox','star','link','trash','calendar','clip','check','settings','compose','date'].map(s=>[s,s])
 cases.push(['attachment-inspector','clip','[data-file="3"]'],['task-editor','check','[data-x="edit-0"]'],['reader-more-mobile','reader','.reader-overflow summary'],['attachment-trash','trash','[data-cmd=attachmentTrash]'],['note-actions','reader','[data-cmd=options]'])
 const outcome=[]
 try{
 const p=await b.newPage()
 await p.goto('http://127.0.0.1:18403/')
 for(const [label,scene,selector] of cases){
  try{
   await p.setViewportSize(label.includes('mobile')?{width:390,height:844}:{width:1440,height:900})
   await p.evaluate(s=>go(s),scene)
   if(selector)await p.locator(selector).first().click({timeout:3500})
   await p.evaluate(l=>document.title='ZH-audit-'+l,label)
   const args=['/d','/c',process.env.ZHIJI_IMPECCABLE,'detect','--cdp',String(port),'--target','ZH-audit-'+label,'--json']
   const {stdout}=await invoke('cmd.exe',args,{timeout:30000,windowsHide:true,maxBuffer:4000000}).catch(e=>{if(e.stdout && Array.isArray(JSON.parse(e.stdout)))return e;throw e})
   outcome.push({label,findings:JSON.parse(stdout)})
  }catch(e){outcome.push({label,error:String(e.stderr||e.message).slice(-700)})}
  fs.writeFileSync(path.join(__dirname,'evidence-r3','detect.json'),JSON.stringify(outcome,null,2))
 }
 console.log(outcome.map(r=>[r.label,r.error||r.findings.length]))
 }finally{await b.close()}
}
run().catch(e=>{console.error(e);process.exitCode=1})
