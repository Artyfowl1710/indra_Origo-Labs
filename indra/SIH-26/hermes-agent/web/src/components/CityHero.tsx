import { useEffect,useRef,useState } from "react";
import { useNavigate } from "react-router";
import { ArrowUpRight,Pause,Play } from "lucide-react";
export function CityHero(){
 const navigate=useNavigate(),video=useRef<HTMLVideoElement>(null);
 const [paused,setPaused]=useState(()=>window.matchMedia("(prefers-reduced-motion: reduce)").matches),[prompt,setPrompt]=useState("");
 useEffect(()=>{if(!video.current)return;if(paused)video.current.pause();else void video.current.play().catch(()=>setPaused(true));},[paused]);
 useEffect(()=>{const media=window.matchMedia("(prefers-reduced-motion: reduce)");const change=()=>{if(media.matches)setPaused(true);};media.addEventListener("change",change);return()=>media.removeEventListener("change",change);},[]);
 useEffect(()=>{const element=video.current;if(!element)return;const observer=new IntersectionObserver(entries=>{if(!entries[0].isIntersecting)element.pause();else if(!paused)void element.play().catch(()=>{});});observer.observe(element);return()=>observer.disconnect();},[paused]);
 return <section className="indra-city-hero" aria-labelledby="city-hero-title">
  <video ref={video} className="indra-city-video" src="/media/indra-city.mp4" poster="/media/indra-city-poster.png" autoPlay={!paused} loop muted playsInline preload="metadata" aria-hidden="true"/>
  <div className="indra-city-veil"/>
  <div className="indra-city-copy"><span className="indra-city-eyebrow">ORIGO LABS / INDRA</span><h1 id="city-hero-title">A world of ideas.<br/>A space to build.</h1><p>Your models, your projects, your next great idea.<br/>Bring them together with Indra.</p>
   <form onSubmit={e=>{e.preventDefault();if(prompt.trim())sessionStorage.setItem("indra-start-draft",prompt.trim());navigate("/chat");}}><label htmlFor="indra-hero-request">What would you like to create?</label><textarea id="indra-hero-request" placeholder="Build something. Explore an idea. Connect the dots." value={prompt} onChange={e=>setPrompt(e.target.value)} rows={2}/><div><span>On-device knowledge · Your choice of model</span><button type="submit">Open workspace <ArrowUpRight size={17}/></button></div></form>
  </div>
  <button className="indra-city-motion" type="button" onClick={()=>setPaused(!paused)} aria-label={paused?"Play city animation":"Pause city animation"}>{paused?<Play size={14}/>:<Pause size={14}/>} {paused?"Play scene":"Pause scene"}</button>
 </section>;
}
