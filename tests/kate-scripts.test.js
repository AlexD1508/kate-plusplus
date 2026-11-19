// Runs the Kate text tools against a minimal fake document/view.
// Usage: node tests/kate-scripts.test.js kate-scripts/kate-plusplus.js
const fs=require('fs');
function Cursor(l,c){this.line=l;this.column=c;}
function Range(a,b,c,d){this.start=new Cursor(a,b);this.end=new Cursor(c,d);}
let text="", sel=null, cur=new Cursor(0,0);
const off=(c)=>{const L=text.split("\n");let o=0;for(let i=0;i<c.line;i++)o+=L[i].length+1;return o+c.column;};
global.Range=Range; global.require=()=>{};
global.document={lines:()=>text.split("\n").length,lineLength:(l)=>text.split("\n")[l].length,line:(l)=>text.split("\n")[l],
 text:(r)=>text.slice(off(r.start),off(r.end)),editBegin(){},editEnd(){},
 removeText:(r)=>{text=text.slice(0,off(r.start))+text.slice(off(r.end));},
 insertText:(c,t)=>{const o=off(c);text=text.slice(0,o)+t+text.slice(o);}};
global.view={hasSelection:()=>!!sel,selection:()=>sel,cursorPosition:()=>cur,removeSelectedText(){}};
const src=fs.readFileSync(process.argv[2],'utf8'); (0,eval)(src);
const t=(name,input,s,exp)=>{text=input;sel=s;try{global[name]();}catch(e){text="THROW:"+e.message}
 const ok=exp===undefined?true:text===exp; console.log((ok?"PASS":"FAIL"),name,JSON.stringify(text).slice(0,80)); if(!ok) process.exitCode=1;};
t("kppFormatJson",'{"a":[1,2],"b":{"c":"ü"}}',null,'{\n    "a": [\n        1,\n        2\n    ],\n    "b": {\n        "c": "ü"\n    }\n}');
t("kppMinifyJson",'{\n "a" : 1 }',null,'{"a":1}');
t("kppFormatJson",'{bad json',null);
t("kppBase64Encode","Grüße 🙂",null,Buffer.from("Grüße 🙂").toString("base64"));
t("kppBase64Decode",Buffer.from("Grüße 🙂 x").toString("base64"),null,"Grüße 🙂 x");
t("kppBase64Decode","SGk",null,"Hi");
t("kppUrlEncode","a b&c=ü",null,"a%20b%26c%3D%C3%BC");
t("kppUrlDecode","a%20b%26c",null,"a b&c");
t("kppRemoveBlankLines","a\n\n  \nb\n",null,"a\nb");
t("kppRemoveDuplicateLines","x\ny\nx\nz\ny",null,"x\ny\nz");
t("kppRemoveDuplicateLines","keep\nkeep\nx\ny\nx\ntail",new Range(2,0,5,0),"keep\nkeep\nx\ny\ntail");
t("kppTrimTrailing","a  \nb\t\nc",null,"a\nb\nc");
t("kppRemoveDuplicateLines","constructor\ntoString\nconstructor",null,"constructor\ntoString");
