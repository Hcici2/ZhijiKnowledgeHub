const paper = document.documentElement.dataset.theme === 'paper'
const paths = {
 book:'M4 19V5a2 2 0 0 1 2-2h14v16H6a2 2 0 0 0 0 4h14M8 8h8M8 12h6',
 inbox:'M4 4h16l2 10v6H2v-6L4 4Zm-2 10h6l2 3h4l2-3h6',
 calendar:'M4 6h16v15H4zM8 3v6m8-6v6M4 11h16',
 link:'M10 13a4 4 0 0 0 6 0l4-4a4 4 0 0 0-6-6l-2 2m2 6a4 4 0 0 0-6 0l-4 4a4 4 0 0 0 6 6l2-2',
 file:'M6 3h8l4 4v14H6zM14 3v5h4M9 12h6m-6 4h6',
 clip:'M8 13l6-6a3 3 0 0 1 4 4l-8 8a5 5 0 0 1-7-7l9-9m-4 13 7-7',
 check:'m3 12 5 5L21 4', star:'m12 3 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z',
 settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm0-5v2m0 14v2M3 12h2m14 0h2M6 6l1 1m10 10 1 1M6 18l1-1M17 7l1-1',
 search:'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Zm5 12 5 5',
 plus:'M12 5v14M5 12h14', filter:'M3 6h18M6 12h12M9 18h6',
 arrow:'m9 6 6 6-6 6', close:'m6 6 12 12M18 6 6 18', trash:'M3 6h18M6 6l1 15h10l1-15M9 6V3h6v3',
 edit:'m4 16 12-12 4 4L8 20H4z', more:'M5 12h1m5 0h1m5 0h1'
}
const icon = (key, n=17) => `<svg aria-hidden="true" width="${n}" height="${n}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round"><path d="${paths[key] || paths.file}"/></svg>`
const notes = [
 ['周五交付新版首页','工作经验','明确新版首页的发布范围、视觉验收和上线前检查。','11 月 18 日','work'],
 ['移动端日历体验','产品灵感','让月份一目了然，选中日期后直接查看当天的记录。','11 月 18 日','idea'],
 ['每周回顾 · 11 月第 3 周','生活记录','记下做得顺利的事，以及下周想留出时间的三件事。','11 月 17 日','life'],
 ['知识库排版参考','学习笔记','整理列表密度、编辑空间以及适合长文的阅读宽度。','11 月 16 日','study'],
 ['常用网站与工具','网站收藏','把常用资源集中记录，随时能找到来源链接。','11 月 16 日','web'],
 ['附件归档规则','工作经验','图片、PDF 与视频按来源笔记归档，定期整理未关联文件。','11 月 15 日','work']
]
const scenes = [['list','知识库'],['reader','双栏阅读'],['date','日期筛选'],['compose','新建笔记'],['calendar','月历'],['settings','设置']]
let scene='list', picked=0, day=18, month=10, year=2026, query='', category='', order='new', range='', setting=0, editing=false
const groups=[['知识空间',[['inbox','收集箱'],['book','我的知识库'],['link','网站与工具'],['clip','附件库']]],['快捷访问',[['star','置顶'],['check','待办事项']]],['系统',[['trash','回收站'],['settings','设置']]]]
const app=document.querySelector('#app')
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))
const action=(id,label,key,cls='')=>`<button type="button" class="btn ${cls}" data-go="${id}">${key?icon(key):''}${label}</button>`
function heading(title,meta,controls=''){
 return `<div class="heading"><div><h1>${title}</h1><p>${meta}</p></div><div class="heading-actions">${controls}</div></div>`
}
function tools(){
 return `<div class="tools"><label class="search">${icon('search')}<input id="search" type="search" aria-label="搜索笔记" placeholder="搜索标题、正文或标签" value="${esc(query)}"></label>
 <button class="btn" data-toggle>筛选</button><select ${filters?"":"hidden"} id="category" aria-label="分类"><option value="">所有分类</option>${[...new Set(notes.map(n=>n[1]))].map(n=>`<option ${n===category?'selected':''}>${n}</option>`).join('')}</select>
 <select ${filters?"":"hidden"} id="order" aria-label="排序"><option value="new">最新在前</option><option value="old" ${order==='old'?'selected':''}>最早在前</option></select>
 ${action(scene==='date'?'list':'date',range||'日期范围','calendar',scene==='date'?'selected':'')}${scene==='date'?dates():''}</div>`
}
function resultRows(){
 let rows=notes.map((n,i)=>[n,i]).filter(([n])=>(!category||n[1]===category)&&n.join(' ').includes(query.trim()))
 if(order==='old')rows.reverse()
 return rows.length?rows.map(([n,i])=>`<button type="button" class="note ${scene==='reader'&&i===picked?'active-note':''}" data-note="${i}"><span class="note-icon ${n[4]}">${icon(i===4?'link':'file',18)}</span><span class="note-main"><strong>${esc(n[0])}</strong><span class="excerpt">${esc(n[2])}</span><span class="metadata"><span class="tag">${esc(n[1])}</span><time>${esc(n[3])}</time></span></span><span class="row-arrow">${icon('arrow',15)}</span></button>`).join(''):'<p class="empty">没有匹配的笔记。试试其他关键词或分类。</p>'
}
function library(){
 return `${heading('我的知识库',notes.length+' 条笔记',`<div class="seg">${action('list','列表',null,'selected')}${action('calendar','日历')}</div>${action('compose','新建笔记','plus','primary')}`)}
 <div class="library ${scene==='reader'?'split':''}"><section class="list-panel">${tools()}<div class="notes" id="notes">${resultRows()}</div></section>${scene==='reader'?reader():''}</div>`
}
function reader(){
 const n=notes[picked]
 return `<article class="reader"><div class="reader-bar"><span>笔记详情</span><div><button class="btn" data-edit>${icon('edit')}编辑</button>${action('list','关闭','close')}</div></div>
 <div class="reader-body"><span class="tag">${esc(n[1])}</span><h2>${esc(n[0])}</h2><div class="reader-meta">${esc(n[3])} · 预计阅读 2 分钟</div>
 <p class="lead">${esc(n[2])}</p><h3>这次要完成的事</h3><ul><li>确认范围、优先级和验收标准。</li><li>检查桌面与移动端的关键交互。</li><li>整理反馈，记录需要跟进的问题。</li></ul>
 <blockquote>每次交付都留下一份可以回看的记录。</blockquote><details><summary>关联笔记 <span>1</span></summary><p>知识库排版参考</p></details><details><summary>待办事项 <span>1</span></summary><p>汇总本周验收结果</p></details></div></article>`
}
function dates(){
 return `<div class="date-panel" role="dialog" aria-label="选择日期范围"><div class="panel-head"><strong>日期范围</strong>${action('list','关闭','close','quiet')}</div>
 <div class="presets">${['不限时间','今天','最近 7 天','最近 30 天','本月'].map(n=>`<button class="btn ${n===(range||'不限时间')?'selected':''}" data-preset="${n}">${n}</button>`).join('')}</div>
 <div class="custom-date"><small>自定义范围</small><div><label>开始日期<input id="start" type="date" value="2026-11-12"></label><label>结束日期<input id="end" type="date" value="2026-11-18"></label></div></div>
 <div class="panel-foot"><span id="date-feedback" role="status"></span><button class="btn primary" data-custom>应用日期</button></div></div>`
}
function calendar(){
 const offset=(new Date(year,month,1).getDay()+6)%7, total=new Date(year,month+1,0).getDate()
 const info=(month===10&&year===2026)?{5:1,12:2,16:3,17:1,18:2,23:1}:{}
 return `${heading('我的知识库','按日期浏览笔记',`<div class="seg">${action('list','列表')}${action('calendar','日历',null,'selected')}</div>${action('compose','记在这一天','plus','primary')}`)}
 <div class="calendar-layout"><section class="calendar-box"><div class="month-head"><strong>${year} 年 ${month+1} 月</strong><div><button class="btn" data-month="-1" aria-label="上个月">‹</button><button class="btn" data-month="1" aria-label="下个月">›</button><button class="btn" data-today>今天</button></div></div>
 <div class="month-grid">${'一二三四五六日'.split('').map(n=>`<span class="weekday">${n}</span>`).join('')}${'<span></span>'.repeat(offset)}
 ${Array.from({length:total},(_,i)=>`<button class="day ${day===i+1?'chosen':''}" data-day="${i+1}" aria-pressed="${day===i+1}"><strong>${i+1}</strong>${info[i+1]?`<small>${info[i+1]} 条</small>`:''}</button>`).join('')}</div></section>
 <section class="day-panel"><h2>${month+1} 月 ${day} 日的笔记</h2><p class="reader-meta">${info[day]||0} 条记录</p>${info[day]?`<div class="notes">${notes.slice(0,Math.min(info[day],3)).map((n,i)=>`<button class="note" data-note="${i}"><span class="note-icon ${n[4]}">${icon('file')}</span><span class="note-main"><strong>${esc(n[0])}</strong><span class="excerpt">${esc(n[2])}</span></span></button>`).join('')}</div>`:'<p class="empty">这一天还没有笔记。</p>'}</section></div>`
}
const sections=[
 ['工作空间',[['默认打开视图','打开知己时优先显示的页面。','我的知识库'],['列表排序','选择新打开列表的排序方式。','最新在前']]],
 ['附件存储',[['存储目录','附件原文件保存在本地。','选择文件夹'],['附件浏览','设置附件库默认展示方式。','列表视图']]],
 ['数据与备份',[['完整备份','导出笔记、分类和附件。','下载备份'],['导入笔记','从已有文件中导入内容。','导入文件']]],
 ['回收站',[['自动清理','从移入回收站起满 30 天后清理。','关闭']]]
]
function settings(){
 return `${heading('设置','管理本地工作空间的显示、附件与数据。')}<div class="settings-layout"><nav aria-label="设置分区">${sections.map(([name],i)=>`<button class="btn ${setting===i?'selected':''}" data-setting="${i}">${name}</button>`).join('')}</nav><section class="settings-panel"><h2>${sections[setting][0]}</h2>${sections[setting][1].map(([title,desc,value])=>`<div class="setting-row"><div><strong>${title}</strong><p>${desc}</p></div><span class="setting-value">${value}</span></div>`).join('')}</section></div>`
}
function compose(){
 const note=editing?notes[picked]:null
 return `<div class="veil"><form class="composer" aria-label="${editing?'编辑笔记':'新建笔记'}"><div class="panel-head"><h2>${editing?'编辑笔记':'新建笔记'}</h2>${action(editing?'reader':'list','关闭','close','quiet')}</div>
 <details class="templates"><summary>从模板开始</summary><div>${['会议记录','学习笔记','每周回顾'].map(n=>`<button type="button" class="btn" data-template="${n}">${n}</button>`).join('')}</div></details>
 <div class="compose-fields"><input name="title" aria-label="标题" placeholder="给笔记起个标题" value="${esc(note?.[0]||'')}"><select name="category" aria-label="笔记分类">${[...new Set(['待整理',...notes.map(n=>n[1])])].map(n=>`<option ${n===note?.[1]?'selected':''}>${esc(n)}</option>`).join('')}</select></div>
 <div class="editor"><div class="formats"><button type="button" data-format="**">加粗</button><button type="button" data-format="# ">H1</button><button type="button" data-format="- ">列表</button><button type="button" data-format="> ">引用</button></div><textarea name="content" aria-label="正文" placeholder="写下一个想法，或贴入一条链接…" required>${esc(note?.[2]||'')}</textarea></div>
 <div class="compose-footer"><label class="btn">${icon('clip')} 选择附件<input type="file" multiple hidden></label><small id="file-count"></small><button class="btn primary" type="submit">保存笔记</button></div></form></div>`
}
function draw(focus){
 app.innerHTML=shell()
 if(focus) app.querySelector(focus)?.focus({preventScroll:true})
}
function go(id){
 scene=id
 history.replaceState(null,'','#'+id)
 draw(id==='compose'?'textarea':undefined)
}
app.addEventListener('click',e=>{
 const target=e.target.closest('button')
 if(!target)return
 const d=target.dataset
 if(d.go){editing=false;go(d.go)}
 if(d.edit!=null){editing=true;go('compose')}
 if(d.note!=null){picked=Number(d.note);go('reader')}
 if(d.setting!=null){setting=Number(d.setting);draw()}
 if(d.preset){range=d.preset==='不限时间'?'':d.preset;go('list')}
 if(d.custom!=null){
   const a=app.querySelector('#start').value,b=app.querySelector('#end').value
   if(!a||!b||a>b){app.querySelector('#date-feedback').textContent='请选择有效的起止日期。';return}
   range=a.slice(5).replace('-','/')+' – '+b.slice(5).replace('-','/');go('list')
 }
 if(d.day){day=Number(d.day);draw()}
 if(d.month){const date=new Date(year,month+Number(d.month),1);year=date.getFullYear();month=date.getMonth();day=1;draw()}
 if(d.today!=null){year=2026;month=10;day=18;draw()}
 if(d.template){app.querySelector('[name=title]').value=d.template;app.querySelector('textarea').value='## 要点\n\n## 下一步\n';app.querySelector('textarea').focus()}
 if(d.format){const editor=app.querySelector('textarea');editor.setRangeText(d.format,editor.selectionStart,editor.selectionEnd,'end');editor.focus()}
})
app.addEventListener('input',e=>{if(e.target.id==='search'){query=e.target.value;app.querySelector('#notes').innerHTML=resultRows()}})
app.addEventListener('change',e=>{
 if(e.target.id==='category')category=e.target.value
 if(e.target.id==='order')order=e.target.value
 if(e.target.id==='category'||e.target.id==='order')app.querySelector('#notes').innerHTML=resultRows()
 if(e.target.type==='file')app.querySelector('#file-count').textContent=e.target.files.length+' 个已选择（演示）'
})
app.addEventListener('submit',e=>{
 e.preventDefault()
 const values=new FormData(e.target)
 const note=[values.get('title').trim()||'未命名笔记',values.get('category'),values.get('content'),'11 月 18 日','work']
 if(editing) notes[picked]=note
 else {notes.unshift(note);picked=0}
 editing=false;query='';category='';go('reader')
})
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&['compose','date','reader'].includes(scene))go('list')})
const pageNames={inbox:'收集箱',list:'我的知识库',link:'网站与工具',clip:'附件库',star:'置顶',check:'待办事项',trash:'回收站',settings:'设置'}
const navTargets={book:'reader',settings:'settings',inbox:'inbox',link:'link',clip:'clip',star:'star',check:'check',trash:'trash'}
let grid=true, preview='', finished=new Set([2]), filters=false
const files=['首页交付清单.pdf','月历草图.svg','阅读排版规范.md','工作区演示.webm']
function attachments(){return heading('附件库','4 个附件',action('clip',grid?'切换为列表':'切换为网格','file'))+'<div class="files '+(grid?'grid':'')+'">'+files.map((f,i)=>'<button class="asset" data-file="'+i+'"><span class="cover">'+(i===1?'<svg viewBox="0 0 160 80"><path d="M0 60Q35 0 80 48T160 20" fill="none" stroke="#768d84" stroke-width="3"/></svg>':icon(i===3?'link':'file',36))+'</span><strong>'+f+'</strong><small>'+esc(notes[i][0])+'</small></button>').join('')+'</div>'+(preview?'<dialog open class="file-preview"><h2>'+preview+'</h2><p>关联笔记 · '+notes[files.indexOf(preview)][0]+'</p>'+action('reader','查看关联笔记','book')+' <button class="btn" data-dismiss>关闭</button></dialog>':'')}
const tasks=['复核日历的年月切换','整理本周阅读摘录','归档首页交付清单']
function taskBoard(){return heading('待办事项','按进度整理笔记中的行动项')+'<div class="taskboard">'+['待完成','已完成'].map((v,g)=>'<section><h2>'+v+'</h2>'+tasks.map((t,i)=>Number(finished.has(i))===g?'<label><input type="checkbox" data-task="'+i+'" '+(g?'checked':'')+'><span>'+t+'<small>'+esc(notes[i][0])+'</small></span></label>':'').join('')+'</section>').join('')+'</div>'}
function shell(){
 const section=pageNames[scene]||'我的知识库'
 let content=scene==='clip'?attachments():scene==='check'?taskBoard():scene==='settings'?settings():scene==='calendar'?calendar():library()
 if(['trash','star','link','inbox'].includes(scene)){let ids={trash:[],star:[1,3],link:[4],inbox:[0,5]}[scene];content=heading(section,ids.length+' 条笔记',action('compose','新建笔记','plus','primary'))+'<div class="collection">'+(ids.map(i=>'<button class="note" data-note="'+i+'">'+icon('file')+'<span class="note-main"><strong>'+esc(notes[i][0])+'</strong><span>'+esc(notes[i][2])+'</span></span></button>').join('')||'<p class="empty">回收站为空。</p>')+'</div>'}
 return '<aside class="sidebar"><div class="brand"><div class="brand-mark">'+icon('book',22)+'</div><div><strong>知己</strong><small>Knowledge Hub</small></div></div>'+groups.map(([label,items])=>'<div class="group"><div class="group-title">'+label+'</div>'+items.map(([key,n])=>'<button title="'+n+'" aria-label="'+n+'" class="nav '+(n===section?'active':'')+'" data-nav="'+navTargets[key]+'">'+icon(key)+'<span>'+n+'</span></button>').join('')+'</div>').join('')+'</aside><div class="workspace"><header class="top">个人空间　/　'+section+'</header><main>'+content+'</main></div>'+(scene==='compose'?compose():'')
}
app.addEventListener('click',e=>{
 const d=e.target.closest('button,input')?.dataset;if(!d)return
 if(d.nav){preview='';go(d.nav)}
 if(d.go==='clip'){grid=!grid;draw()}
 if(d.file!=null){picked=Number(d.file);preview=files[picked];draw()}
 if(d.dismiss!=null){preview='';draw()}
 if(d.task!=null){let i=Number(d.task);finished.has(i)?finished.delete(i):finished.add(i);draw()}
 if(d.toggle!=null){filters=!filters;draw()}
})
go(location.hash.slice(1)||'reader')
