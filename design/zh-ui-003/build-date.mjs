import {createRequire} from 'node:module'
import {fileURLToPath,pathToFileURL} from 'node:url'
import {mkdtemp,copyFile} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {dirname,resolve} from 'node:path'
const root=dirname(fileURLToPath(import.meta.url))
const req=createRequire(resolve(root,'../../frontend/package.json'))
const {build}=await import(pathToFileURL(req.resolve('vite')).href)
const {default:vue}=await import(pathToFileURL(req.resolve('@vitejs/plugin-vue')).href)
const output=await mkdtemp(resolve(tmpdir(),'zh-date-build-'))
await build({configFile:false,root,plugins:[vue()],resolve:{alias:{vue:req.resolve('vue/dist/vue.runtime.esm-bundler.js')}},define:{'process.env.NODE_ENV':'"production"'},build:{outDir:output,emptyOutDir:false,lib:{entry:resolve(root,'date-entry.mjs'),formats:['iife'],name:'ZhRange',fileName:()=> 'date-control.js',cssFileName:'date-control'}}})
for(const name of ['date-control.js','date-control.css']) await copyFile(resolve(output,name),resolve(root,name))
