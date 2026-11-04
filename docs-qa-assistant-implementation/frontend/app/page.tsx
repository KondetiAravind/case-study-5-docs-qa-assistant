"use client";
import {useEffect,useState} from "react";
const API=process.env.NEXT_PUBLIC_API_URL||"http://localhost:8000";
type DemoUser={id:string;label:string;role:string};
type Source={doc_id:string;title:string;excerpt:string;relevance_score:number};
type Result={status:string;answer:string;sources:Source[];mode:string;request_id:string};
export default function Home(){
 const [users,setUsers]=useState<DemoUser[]>([]),[user,setUser]=useState("standard");
 const [question,setQuestion]=useState(""),[result,setResult]=useState<Result|null>(null);
 const [loading,setLoading]=useState(false),[error,setError]=useState(""),[feedback,setFeedback]=useState("");
 useEffect(()=>{fetch(`${API}/api/demo-users`).then(r=>r.json()).then(setUsers).catch(()=>setError("Cannot connect to API. Start the backend and check NEXT_PUBLIC_API_URL."));},[]);
 async function ask(e:React.FormEvent){e.preventDefault();if(question.trim().length<3)return;setLoading(true);setError("");setResult(null);setFeedback("");
  try{const response=await fetch(`${API}/api/ask`,{method:"POST",headers:{"Content-Type":"application/json","X-Demo-User":user},body:JSON.stringify({question})});
   const body=await response.json();if(!response.ok)throw new Error(body.detail||"Request failed");setResult(body);
  }catch(err){setError(err instanceof Error?err.message:"Something went wrong.");}finally{setLoading(false);}}
 async function sendFeedback(helpful:boolean){if(!result)return;try{await fetch(`${API}/api/feedback`,{method:"POST",headers:{"Content-Type":"application/json","X-Demo-User":user},body:JSON.stringify({request_id:result.request_id,helpful})});setFeedback("Thanks — feedback received.");}catch{setFeedback("Feedback could not be sent.");}}
 return <main className="shell">
  <header className="topbar"><div className="brandmark">S</div><div><div className="brand">SOLSTICE LEARNING</div><div className="subbrand">KNOWLEDGE ASSISTANT</div></div><span className="demoTag">DEMO ENVIRONMENT</span></header>
  <section className="hero"><p className="eyebrow">SUPPORT KNOWLEDGE, SIMPLIFIED</p><h1>What can I help<br/><span>you find today?</span></h1><p className="intro">Ask a question about Solstice Learning. Answers are grounded in the documentation your role is allowed to access.</p></section>
  <section className="panel"><div className="roleRow"><label htmlFor="role">Demo identity</label><select id="role" value={user} onChange={e=>{setUser(e.target.value);setResult(null);}}>{users.map(u=><option key={u.id} value={u.id}>{u.label} · {u.role}</option>)}</select></div>
   <form onSubmit={ask}><label className="questionLabel" htmlFor="question">YOUR QUESTION</label><textarea id="question" value={question} onChange={e=>setQuestion(e.target.value)} placeholder="e.g. How long does a password reset link remain valid?" maxLength={1000} rows={3}/>
    <div className="formBottom"><span>{question.length}/1000 characters</span><button disabled={loading||question.trim().length<3}>{loading?"Searching...":"Ask assistant  →"}</button></div></form>
  </section>
  {error&&<div className="error">{error}</div>}
  {result&&<section className={`answerCard ${result.status==="not_found"?"abstain":""}`}>
   <div className="answerMeta"><span>{result.status==="answered"?"ANSWER FOUND":"NO SUPPORTED ANSWER"}</span><span className="mode">{result.mode==="groq"?"GROQ-GENERATED":result.mode==="extractive"?"SOURCE-BASED FALLBACK":"SAFE ABSTENTION"}</span></div>
   <div className="answerText">{result.answer}</div>
   {result.sources.length>0&&<div className="sources"><h3>Supporting documentation</h3>{result.sources.map(s=><article className="source" key={s.doc_id}><div><b>{s.title}</b><span>{s.doc_id}</span></div><p>{s.excerpt}</p></article>)}</div>}
   <div className="feedback"><span>Was this helpful?</span><button className="feedbackBtn" onClick={()=>sendFeedback(true)}>Yes</button><button className="feedbackBtn" onClick={()=>sendFeedback(false)}>No</button><small>{feedback}</small></div>
  </section>}
  <footer><span>Grounded in approved documentation</span><span>Access-aware · Evidence-first · No guessing</span></footer>
 </main>;
}
