// Runtime template smoke tests with a minimal DOM stub; not a browser/layout test.
class StubNode {
 constructor(){this.innerHTML='';this.value='';this.className='';this.textContent='';this.classList={toggle:()=>false};}
 querySelector(selector){return document.querySelector(selector);}
 querySelectorAll(){return [];}
 addEventListener(){}
 setAttribute(){}
 removeAttribute(){}
 showModal(){this.open=true;}
 close(){this.open=false;}
}
const nodes=new Map();
const document={querySelector(selector){if(!nodes.has(selector))nodes.set(selector,new StubNode());return nodes.get(selector);},querySelectorAll(){return [];}};
const window={addEventListener(){}};
