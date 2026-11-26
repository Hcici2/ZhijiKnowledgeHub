/* Offline interaction fixtures; no application API or account data. */
window.R2Extras = (() => {
  const fileNames = ['首页交付清单.pdf','月历草图.svg','阅读排版规范.md','工作区演示.webm']
  const sources = ['周五交付新版首页','移动端日历体验','每周回顾 · 11 月第 3 周','知识库排版参考']
  const files = fileNames.map((name,i)=>({id:i,name,kind:['PDF','图片','文档','视频'][i],size:['186 KB','685 B','8 KB','27 KB'][i],date:'2026-11-'+(18-i),source:sources[i]}))
  const titles = ['复核日历的年月切换','整理本周阅读摘录','归档首页交付清单','补充交付前检查项','记录阅读时遇到的问题','核对文字与底色的对比度','回看工作区演示','梳理移动端的导航路径','摘录三段有启发的文字','整理本周学习日志','为手稿建立索引','挑选首页的示意图','给文章补充出处','检查引用链接','精简知识库分类','回访上次讨论的问题','整理月底复盘提纲','补齐设计评审记录','归档访谈提纲','检查导出文件格式','准备下一次周会','汇总原型反馈','整理用户观察笔记','完善读书目录']
  const tasks = titles.map((title,id)=>({id,title,date:['2026-11-18','2026-11-17','','2026-11-20','2026-11-22',''][id%6],done:id===2||id>20,source:sources[id%4]}))
  const x = {grid:true,fileSearch:'',kind:'全部类型',from:'',to:'',preview:null,page:'工作空间',taskSearch:'',period:'全部日期',batch:false,selected:new Set(),dense:'舒适',limit:'20',retain:false,folder:'默认目录',categories:['学习笔记','工作经验','个人灵感','生活记录'],status:''}
  let scene, previous, taskEditor=null, bulkDate=false, undo=[]
  const escape = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))
  const button=(key,label)=>'<button type="button" data-x="'+key+'">'+label+'</button>'
  const select=(id,items,value)=>'<select aria-label="'+id+'" data-select="'+id+'">'+items.map(v=>'<option '+(v===value?'selected':'')+'>'+v+'</option>').join('')+'</select>'
  const find=(id,value)=>'<input type="search" data-find="'+id+'" aria-label="'+id+'" placeholder="'+id+'" value="'+escape(value)+'">'
  const top=(title,meta,actions='')=>'<header class="ex-head"><div><h1>'+title+'</h1><p>'+meta+'</p></div><div>'+actions+'</div></header>'
  const tick=(id)=>x.batch?'<input type="checkbox" aria-label="选择项目" data-tick="'+id+'" '+(x.selected.has(id)?'checked':'')+'>':''
  const batch=()=>button('batch',x.batch?'退出多选':'批量管理')+(x.batch?button('all','全选')+button('act',scene==='check'?'标为完成':'移入回收站')+(scene==='check'?button('reschedule','调整到期日'):''):'')
  const filteredFiles=()=>files.filter(f=>!f.deleted&&f.name.includes(x.fileSearch)&&(x.kind==='全部类型'||f.kind===x.kind)&&(!x.from||f.date>=x.from)&&(!x.to||f.date<=x.to))
  function thumb(f){
    if(f.id===1)return '<img src="media/study.svg" alt="等轴结构设计手稿">'
    if(f.id===3)return '<img src="media/workspace.jpg" alt="工作区演示首帧"><span class="ex-runtime">▶　0:05</span>'
    return f.id===0?'<div class="ex-paper"><small>RELEASE NOTES</small><b>首页交付清单</b><hr>01　视觉与布局<br>02　交互与反馈<br>03　发布与回滚</div>':'<div class="ex-markdown"><small>Markdown</small><b># 阅读排版</b><span>## 正文层级</span><span>行宽与段落节奏</span></div>'
  }
  function filePage(){
    const items=filteredFiles(),f=files.find(f=>f.id===x.preview&&!f.deleted)
    return top('附件库',files.filter(f=>!f.deleted).length+' 个文件',batch())+'<div class="ex-tools">'+find('搜索文件',x.fileSearch)+select('文件类型',['全部类型','图片','视频','PDF','文档'],x.kind)+'<span data-range-control data-label="上传日期" data-from="'+x.from+'" data-to="'+x.to+'"></span>'+button('layout',x.grid?'列表视图':'网格视图')+'</div><div class="ex-file-layout"><div class="ex-files '+(x.grid?'grid':'list')+'">'+items.map(f=>'<div class="ex-file">'+tick(f.id)+'<button class="ex-open" data-file="'+f.id+'"><span class="ex-thumb t'+f.id+'">'+thumb(f)+'</span><strong>'+f.name+'</strong><small>'+f.kind+' · '+f.size+' · '+f.date.slice(5)+'</small><small>'+f.source+'</small></button></div>').join('')+(items.length?'':'<p>没有符合条件的文件。</p>')+'</div>'+(f?'<aside class="ex-inspect">'+button('dismiss','关闭详情')+'<h2>'+f.name+'</h2>'+(f.id===3?'<video controls src="media/workspace.webm" poster="media/workspace.jpg"></video>':'<div class="ex-thumb">'+thumb(f)+'</div>')+'<dl><dt>类型与大小</dt><dd>'+f.kind+' · '+f.size+'</dd><dt>上传日期</dt><dd>'+f.date+'</dd><dt>关联笔记</dt><dd><button data-source="'+escape(f.source)+'">'+escape(f.source)+'</button></dd></dl><details><summary>更多操作</summary>'+button('trashfile','移入回收站')+'</details></aside>':'')+'</div>'
  }
  const group=t=>t.done?'已完成':!t.date?'未安排':t.date<'2026-11-18'?'逾期':t.date==='2026-11-18'?'今天':'即将到期'
  const periods=['今天','逾期','即将到期','未安排','已完成']
  const filteredTasks=()=>tasks.filter(t=>(t.title+' '+t.source).includes(x.taskSearch)&&(x.period==='全部日期'||group(t)===x.period))
  function taskPage(){
    const visible=filteredTasks()
    const draft=tasks.find(t=>t.id===taskEditor); const form=(draft||bulkDate)?'<dialog open class="ex-edit"><form data-task-form><h2>'+(draft?'编辑任务':'批量调整到期日')+'</h2>'+(draft?'<label>任务标题<input required name="title" value="'+escape(draft.title)+'"></label>':'')+'<label>到期日<input type="date" name="date" value="'+(draft?.date||'')+'"></label>'+(draft?'<label>时间<input type="time" name="time" value="'+(draft.time||'')+'"></label><label>优先级<select name="priority">'+['普通','重要','紧急'].map(v=>'<option '+(v===draft.priority?'selected':'')+'>'+v+'</option>').join('')+'</select></label>':'')+'<div>'+button('canceledit','取消')+' <button type="submit">保存</button></div></form></dialog>':''; return form+top('待办事项',tasks.length+' 项任务　·　'+tasks.filter(t=>!t.done).length+' 项待完成',(undo.length?button('undo','撤销上次修改'):'')+batch())+'<div class="ex-tools">'+find('搜索任务或笔记',x.taskSearch)+select('任务日期',['全部日期',...periods],x.period)+'</div><div class="ex-groups">'+periods.map(g=>{const rows=visible.filter(t=>group(t)===g);return rows.length?'<section><h2>'+g+' <small>'+rows.length+'</small></h2>'+rows.map(t=>'<div class="ex-task">'+tick(t.id)+'<input type="checkbox" aria-label="完成任务" data-done="'+t.id+'" '+(t.done?'checked':'')+'><span class="'+(t.done?'done':'')+'">'+escape(t.title)+'</span><button class="ex-source" data-source="'+escape(t.source)+'">'+escape(t.source)+'</button><time>'+escape([t.date.slice(5),t.time,t.priority].filter(Boolean).join(' ')||'—')+'</time>'+button('edit-'+t.id,'编辑')+'</div>').join('')+'</section>':''}).join('')+(visible.length?'':'<p>没有匹配的任务。</p>')+'</div>'
  }
  const groups=['工作空间','分类管理','附件存储','导入与备份','回收站']
  const row=(label,desc,ctrl)=>'<div class="ex-setting"><div><h3>'+label+'</h3><p>'+desc+'</p></div>'+ctrl+'</div>'
  function settingsPage(){
    const config=[
      row('数据概览','当前原型示例','<span>'+((typeof notes!=='undefined'&&notes.length)||sources.length)+' 条笔记 · '+files.filter(f=>!f.deleted).length+' 个附件 · '+tasks.length+' 项待办</span>')+row('列表密度','示例工作空间的显示偏好。',select('列表密度',['舒适','紧凑'],x.dense))+row('每页笔记数','设置分页时显示的结果数。',select('每页笔记数',['10','20','50'],x.limit)),
      row('知识分类',x.categories.map(escape).join('　·　'),button('addcat','新增分类')),
      row('附件存放位置',escape(x.folder),'<label class="ex-action">选择目录<input hidden type="file" webkitdirectory data-folder></label>')+row('默认位置','恢复示例目录配置。',button('resetfolder','恢复默认')),
      row('导入笔记','选择文件后查看文件名，原型不写入数据库。','<label class="ex-action">选择文件<input type="file" hidden data-import></label>')+row('备份','下载当前演示配置。',button('backup','导出配置')),
      row('30 天后自动清理','此开关只记录演示偏好。','<input type="checkbox" role="switch" aria-label="30 天后自动清理" data-retain '+(x.retain?'checked':'')+'>')+row('清空附件回收站',files.filter(f=>f.deleted&&!f.purged).length+' 个演示文件',button('purge','清空回收站'))+files.filter(f=>f.deleted&&!f.purged).map(f=>row(f.name,'已删除的演示附件',button('recover-'+f.id,'恢复'))).join('')
    ]
    return top('设置','管理个人工作空间')+'<div class="ex-settings"><nav>'+groups.map(g=>'<button data-pref="'+g+'" aria-current="'+(x.page===g)+'">'+g+'</button>').join('')+'</nav><section><h2>'+x.page+'</h2>'+config[groups.indexOf(x.page)]+'</section></div>'
  }
  function render(id){scene=id;if(previous!==id){x.selected.clear();x.batch=false;x.status='';taskEditor=null;bulkDate=false;previous=id}return '<section class="extra" data-extra>'+({clip:filePage,check:taskPage,settings:settingsPage}[id]())+'<output aria-live="polite">'+escape(x.status)+'</output></section>'}
  function bind(){
    const host=document.querySelector('[data-extra]');if(!host)return
    host.addEventListener('rangechange',e=>{x.from=e.detail.from;x.to=e.detail.to;draw()})
    host.onsubmit=e=>{if(!e.target.matches('[data-task-form]'))return;e.preventDefault();const form=new FormData(e.target);const ids=bulkDate?[...x.selected]:[taskEditor];undo=ids.map(id=>({...tasks[id]}));ids.forEach(id=>{const t=tasks[id];t.date=form.get('date');if(!bulkDate){t.title=form.get('title').trim();t.time=form.get('time');t.priority=form.get('priority')}});taskEditor=null;bulkDate=false;draw()}
    host.oninput=e=>{const k=e.target.dataset.find;if(!k)return;x[k==='搜索文件'?'fileSearch':'taskSearch']=e.target.value;const pos=e.target.selectionStart;draw();const f=document.querySelector('[data-find]');f.focus();f.setSelectionRange(pos,pos)}
    host.onchange=e=>{const d=e.target.dataset;if(d.select)x[{'文件类型':'kind','任务日期':'period','每页笔记数':'limit','列表密度':'dense'}[d.select]]=e.target.value
      else if(d.done!==undefined){undo=[{...tasks[+d.done]}];tasks[+d.done].done=e.target.checked}
      else if(d.tick!==undefined){e.target.checked?x.selected.add(+d.tick):x.selected.delete(+d.tick)}
      else if(d.folder!==undefined){x.folder=e.target.files[0]?.webkitRelativePath.split('/')[0]||x.folder}
      else if(d.import!==undefined)x.status='已选择 '+(e.target.files[0]?.name||'')
      else if(d.retain!==undefined)x.retain=e.target.checked
      else return;draw()}
    host.onclick=e=>{const b=e.target.closest('button');if(!b)return;const d=b.dataset,k=d.x
      if(d.source){window.openNoteByTitle?.(d.source);return} else if(d.pref)x.page=d.pref
      else if(d.file!==undefined){const id=+d.file;if(x.batch){x.selected.has(id)?x.selected.delete(id):x.selected.add(id)}else x.preview=id}
      else if(k==='batch'){x.batch=!x.batch;x.selected.clear()}
      else if(k==='all'){for(const r of scene==='clip'?filteredFiles():filteredTasks())x.selected.add(r.id)}
      else if(k==='act'){if(!x.selected.size){x.status='请先选择项目。'}else if(scene==='check'){undo=[...x.selected].map(id=>({...tasks[id]}));for(const id of x.selected)tasks[id].done=true;x.selected.clear()}else if(confirm('将选中的附件移入演示回收站？')){files.forEach(f=>{if(x.selected.has(f.id))f.deleted=true});x.selected.clear()}}
      else if(k==='trashfile'){if(confirm('将此附件移入演示回收站？')){files[x.preview].deleted=true;x.preview=null}}
      else if(k==='layout')x.grid=!x.grid
      else if(k==='dismiss')x.preview=null
      else if(k==='undo'){undo.forEach(t=>Object.assign(tasks[t.id],t));undo=[]}
      else if(k==='reschedule'){bulkDate=x.selected.size>0;if(!bulkDate)x.status='请先选择任务。'}
      else if(k==='canceledit'){taskEditor=null;bulkDate=false}
      else if(k?.startsWith('recover-')){files[Number(k.slice(8))].deleted=false}
      else if(k?.startsWith('edit-'))taskEditor=Number(k.slice(5))
      else if(k==='addcat'){const c=prompt('分类名称');if(c?.trim()&&!x.categories.includes(c.trim()))x.categories.push(c.trim())}
      else if(k==='resetfolder')x.folder='默认目录'
      else if(k==='purge'){if(confirm('永久删除演示回收站内的附件？')){files.forEach(f=>{if(f.deleted)f.purged=true});x.status='已清空演示回收站。'}}
      else if(k==='backup'){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify({categories:x.categories,density:x.dense,pageSize:x.limit,retention:x.retain},null,2)],{type:'application/json'}));a.download='知己-演示配置.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
      else return;draw()}
  }
  return {render,bind,samples:()=>({tasks:tasks.map(t=>({...t})), files:files.map(f=>({...f}))})}
})()
