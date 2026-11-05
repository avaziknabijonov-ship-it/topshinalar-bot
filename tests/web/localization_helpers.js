'use strict';
const fs=require('node:fs');
const vm=require('node:vm');
module.exports=context=>{
  context.window ||= {};
  context.window.WorkspaceTextData=JSON.parse(fs.readFileSync('locales/uz-ru.json','utf8'));
  vm.runInContext(fs.readFileSync('web/ui-text.js','utf8'),context);
  context.WorkspaceText=context.window.WorkspaceText;
};
