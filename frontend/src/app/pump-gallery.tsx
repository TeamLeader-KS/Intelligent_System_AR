import {useEffect,useState} from "react";
import type {CSSProperties} from "react";
import {useQuery} from "@tanstack/react-query";
import {useRepository} from "./context";

function externalLink(value:string):string|undefined {
 try{const url=new URL(value);return url.protocol==="https:"||url.protocol==="http:"?url.toString():undefined;}
 catch{return undefined;}
}

function localImage(value:string):string|undefined {
 try{const url=new URL(value,window.location.origin);return url.origin===window.location.origin?url.toString():undefined;}
 catch{return undefined;}
}

export function PumpGallery() {
 const repo=useRepository();const gallery=useQuery({queryKey:["demo-pumps"],queryFn:()=>repo.demoPumps()});
 const [selected,setSelected]=useState(()=>new URLSearchParams(window.location.search).get("sample")||"");
 const [scale,setScale]=useState(100);const [ratio,setRatio]=useState(1.5);
 const [showPlate,setShowPlate]=useState(true);const [showQr,setShowQr]=useState(true);
 const [chosenPlateSize,setChosenPlateSize]=useState<number|null>(null);const [qrError,setQrError]=useState(false);
 const [plateOffset,setPlateOffset]=useState(22);
 const [imageError,setImageError]=useState(false);
 const [viewport,setViewport]=useState(()=>({width:window.innerWidth,height:window.innerHeight}));
 useEffect(()=>{
  const resize=()=>setViewport({width:window.innerWidth,height:window.innerHeight});
  const navigate=()=>setSelected(new URLSearchParams(window.location.search).get("sample")||"");
  window.addEventListener("resize",resize);window.addEventListener("popstate",navigate);
  return()=>{window.removeEventListener("resize",resize);window.removeEventListener("popstate",navigate);};
 },[]);
 const items=gallery.data?.items||[];
 const item=items.find(item=>item.id===selected)||items[0];
 useEffect(()=>{setScale(100);setImageError(false);setQrError(false);setRatio(1.5);},[item?.id]);
 const choose=(id:string)=>{
  setSelected(id);const url=new URL(window.location.href);url.searchParams.set("sample",id);window.history.replaceState(null,"",url);
 };
 const image=item?localImage(item.image_url):undefined;
 const width=Math.min(Math.max(240,viewport.width-32),Math.max(240,viewport.height-210)*ratio,1800)*scale/100;
 const inventory=item?.inventory_number||"pump_demo_001";
 const serial=item?.serial_number||"DEMO-PUMP-2026-001";
 const plateSize=chosenPlateSize??(viewport.width<600?95:60);
 // Leave a 2% inset on each side even at the slider's maximum size.
 const plateWidth=width*.96*plateSize/100;
 const qrSize=Math.max(24,Math.min(112,plateWidth*.22));
 const plateFont=Math.min(26,Math.max(7,(plateWidth-(showQr?qrSize+6:0)-18)/((Math.max(serial.length,inventory.length)+5)*.64)));
 const plateStyle={width:showPlate?`${plateSize*.96}%`:`${qrSize+18}px`,"--plate-font":`${plateFont}px`,"--plate-qr":`${qrSize}px`,"--plate-offset":`${plateOffset}%`} as CSSProperties;
 const qrUrl=localImage(item?.qr_url||"/industrial-vision/demo-qr.svg");
 return <div className="pump-gallery"><header><a href="/industrial-vision/">← На главную</a><span>Примеры для живой камеры телефона</span></header><main>
  <h1>Варианты центробежного насосного агрегата</h1>
  <p>Откройте изображение на ноутбуке и наведите камеру телефона. Здесь нет результатов распознавания и готовых рамок.</p>
  {gallery.isPending?<p role="status">Загружаем примеры…</p>:gallery.isError?<section className="panel"><p role="alert" className="error">{gallery.error instanceof Error?gallery.error.message:"Не удалось загрузить примеры. Проверьте запуск локального сервера."}</p><button onClick={()=>void gallery.refetch()}>Повторить</button></section>:
   items.length===0?<section className="panel"><p>Примеры насосов пока не подготовлены.</p></section>:item&&<>
   <div className="gallery-controls"><label>Пример насоса<select value={item.id} onChange={event=>choose(event.target.value)}>{items.map(pump=><option key={pump.id} value={pump.id}>{pump.name}</option>)}</select></label>
    <div className="gallery-scale"><button className="secondary" aria-label="Уменьшить изображение" disabled={scale<=25} onClick={()=>setScale(value=>Math.max(25,value-10))}>−</button>
     <label>Масштаб<input type="range" min={25} max={200} step={5} value={scale} onChange={event=>setScale(Number(event.target.value))}/></label><output aria-live="polite">{scale}%</output>
     <button className="secondary" aria-label="Увеличить изображение" disabled={scale>=200} onClick={()=>setScale(value=>Math.min(200,value+10))}>+</button>
     <button className="secondary" onClick={()=>setScale(100)}>По размеру экрана</button></div>
    <label className="gallery-plate-size">Размер шильдика: {plateSize}%<input aria-label="Размер шильдика" type="range" min={25} max={100} step={5} value={plateSize} onChange={event=>setChosenPlateSize(Number(event.target.value))}/></label>
    <label className="gallery-plate-size">Высота шильдика: {plateOffset}%<input aria-label="Высота шильдика" type="range" min={2} max={50} step={1} value={plateOffset} onChange={event=>setPlateOffset(Number(event.target.value))}/></label>
   </div>
   {selected&&!items.some(pump=>pump.id===selected)&&<p className="notice">Запрошенный пример не найден. Показан первый доступный насос; выберите нужное изображение.</p>}
   <div className="actions gallery-toggles"><button className="secondary" aria-pressed={showPlate} onClick={()=>setShowPlate(value=>!value)}>{showPlate?"Скрыть учебный шильдик":"Показать учебный шильдик"}</button>
    <button className="secondary" aria-pressed={showQr} onClick={()=>setShowQr(value=>!value)}>{showQr?"Скрыть учебный QR":"Показать учебный QR"}</button>
    {image&&<a className="button secondary" href={image} target="_blank" rel="noreferrer">Оригинальный размер ↗</a>}</div>
   <p className="gallery-binding">Учебная привязка к <strong>{inventory}</strong>, не идентификация реального фото. Шильдик и QR нанесены поверх изображения как демонстрационный макет, а не паспорт изображённого насоса.</p>
   <div className="gallery-image-viewport"><div className="gallery-scene" style={{width}}>
   <div className="gallery-photo">
    {image&&!imageError?<img key={item.id} className="gallery-pump-image" src={image} alt={item.name} onLoad={event=>setRatio(event.currentTarget.naturalWidth/event.currentTarget.naturalHeight||1.5)} onError={()=>setImageError(true)}/>:<p role="alert" className="error">Изображение примера недоступно. Выберите другой насос или повторите загрузку страницы.</p>}
    {(showPlate||showQr)&&<div className="gallery-demo-plate" data-position={item.plate_position||"bottom-right"} style={plateStyle} aria-label="Учебный шильдик поверх оборудования">
     {showPlate&&<div className="gallery-plate-text"><span>DEMO · УЧЕБНЫЙ МАКЕТ</span><strong>S/N: {serial}</strong><strong>INV: {inventory}</strong><small>НЕ ЗАВОДСКАЯ ТАБЛИЧКА</small></div>}
     {showQr&&<div className="gallery-demo-qr">{qrUrl&&!qrError?<img src={qrUrl} alt={`Учебный QR: ${inventory}`} onError={()=>setQrError(true)}/>:<small>QR ещё не подготовлен</small>}</div>}
    </div>}
   </div></div></div>
   <section className="gallery-attribution"><h2>{item.name}</h2><p>{item.description}</p><p><strong>{item.synthetic?"Синтетическое демонстрационное изображение":"Фотография из открытого источника"}</strong></p>
    {(item.case_groups||[]).length>0&&<p>Группы примеров: {item.case_groups!.join(" · ")}</p>}
    {(item.expected_observations||[]).length>0&&<><h3>На что обратить внимание</h3><ul>{item.expected_observations!.map((value,index)=><li key={index}>{value}</li>)}</ul><p>Это подсказки для проверки сценария, не эталонная разметка и не подтверждение неисправности. Невидимые по фото утечки и внутренние дефекты не утверждаются.</p></>}
    <p>Автор: {item.author||"Не указан"} · Лицензия: {externalLink(item.license_url)?<a href={externalLink(item.license_url)} target="_blank" rel="noreferrer">{item.license||"Условия использования"} ↗</a>:item.license||"Не указана"}</p>
    {externalLink(item.source_url)&&<p><a href={externalLink(item.source_url)} target="_blank" rel="noreferrer">Источник изображения ↗</a></p>}
    <p>Изображения предназначены для демонстрации. Распознавание с экрана не заменяет проверку качества на реальном оборудовании.</p>
   </section>
  </>}
 </main></div>;
}
