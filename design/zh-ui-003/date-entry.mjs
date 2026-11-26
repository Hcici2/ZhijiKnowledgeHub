import {createApp,h} from 'vue'
import Picker from '../../frontend/src/components/DateRangePicker.vue'
const mounted=new Map()
const key=d=>[String(d.getFullYear()).padStart(4,'0'),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-')
export function mountAll(){
 for(const [el,app] of mounted)if(!el.isConnected){app.unmount();mounted.delete(el)}
 for(const el of document.querySelectorAll('[data-range-control]')){
  if(mounted.has(el))continue
  const apply=(from,to)=>el.dispatchEvent(new CustomEvent('rangechange',{bubbles:true,detail:{from,to}}))
  const preset=p=>{const start=new Date(),end=new Date(start);if(p==='all')return apply('','');if(p==='week')start.setDate(start.getDate()-6);if(p==='month-days')start.setDate(start.getDate()-29);if(p==='month'){start.setDate(1);end.setMonth(end.getMonth()+1,0)}apply(key(start),key(end))}
  const app=createApp({render:()=>h(Picker,{from:el.dataset.from||'',to:el.dataset.to||'',label:el.dataset.label||'日期范围',onApply:apply,onPreset:preset})})
  app.config.idPrefix='range-'+mounted.size
  app.mount(el);mounted.set(el,app)
 }
}
