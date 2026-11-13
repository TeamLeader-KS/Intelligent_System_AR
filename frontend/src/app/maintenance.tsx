import {useState} from "react";
import {useQuery,useQueryClient} from "@tanstack/react-query";
import {useRepository} from "./context";
import {PassportFacts} from "./passport-facts";
import type {ComponentWorkInput,Diagnostic,DiagnosticPreview,EquipmentCard,EquipmentComponent,SensorReading,VisualCheck,WorkAction} from "../domain/models";

const workNames:Record<WorkAction,string>={INSPECTED:"Проверен",SERVICED:"Обслуживание",REPLACED:"Замена",READINGS:"Ввод наработки",STARTED:"Запустить счёт моточасов",STOPPED:"Остановить счёт моточасов"};
const statuses:Record<string,string>={OK:"Видимых проблем не обнаружено",WARNING:"Рекомендуется проверка",CRITICAL:"Признаки возможного дефекта",UNKNOWN:"Недостаточно данных",DUE:"Норматив достигнут",APPROACHING:"Приближается норматив",WITHIN_NORM:"В пределах норматива",INSUFFICIENT_DATA:"Недостаточно данных"};
const units:Record<string,string>={hours:"ч",days:"дней",cycles:"циклов"};
const parameters:Record<string,string>={vibration_mm_s:"Виброскорость",vibration_axial_mm_s:"Осевая вибрация",vibration_low_mm_s:"Низкочастотная вибрация",vibration_hf_mm_s:"Высокочастотная вибрация",bearing_temperature_c:"Температура подшипника",current_a:"Ток",inlet_pressure_bar:"Давление на входе",efficiency_pct:"КПД",phase_imbalance_pct:"Дисбаланс токов фаз",pressure_bar:"Давление электронного датчика",gauge_pressure_bar:"Давление на манометре"};
const physicalUnits:Record<string,string>={C:"°C",A:"А",bar:"бар","mm/s":"мм/с"};
const time=(value:string|null|undefined)=>value?value.length===10?value.split("-").reverse().join("."):new Date(value).toLocaleString("ru-RU"):"Не указано";
const number=(value:number|null|undefined)=>value==null?"Не указано":value.toLocaleString("ru-RU",{maximumFractionDigits:2});
const errorMessage=(error:unknown)=>error instanceof Error?error.message:"Не удалось выполнить запрос";

function requestKey():string {
 const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
 const hex=Array.from(bytes,b=>b.toString(16).padStart(2,"0")).join("");
 return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}

function Pagination({offset,total,onChange,pending}:{offset:number;total:number;onChange:(offset:number)=>void;pending:boolean}) {
 return <div className="actions pagination"><button className="secondary" disabled={pending||offset===0} onClick={()=>onChange(Math.max(0,offset-20))}>Назад</button>
 <span>{total?`${offset+1}–${Math.min(offset+20,total)} из ${total}`:"Записей нет"}</span>
 <button className="secondary" disabled={pending||offset+20>=total} onClick={()=>onChange(offset+20)}>Далее</button></div>;
}

function Diagnostics({items}:{items:Diagnostic[]}) {
 return <>{items.map(item=><article className={`finding ${item.status==="CRITICAL"?"critical":"warning"}`} key={item.code}>
  <strong>{item.title}</strong><p>{statuses[item.status]||item.status} · предварительное правило</p>
  <p>{item.reason}</p><p>{item.recommendation}</p></article>)}</>;
}

function ComponentCard({component}:{component:EquipmentComponent}) {
 const resource=component.resource;
 return <><h3>{component.name}</h3><p>{component.model}</p>
 <PassportFacts data_origin={component.data_origin} facts={component.facts}/>
 <div className="facts"><div><small>Состояние счётчика</small><strong>{component.runtime_state==="RUNNING"?"В работе — часы считаются":"Остановлен — часы не считаются"}</strong></div>
 <div><small>Наработка</small><strong>{number(component.operating_hours)} ч</strong></div>
 <div><small>Дата установки</small><strong>{time(component.installed_on)}</strong></div><div><small>Последнее обслуживание</small><strong>{time(component.last_serviced_at)}</strong></div></div>
 <h3>Параметры и уставки</h3>{component.specifications.length===0?<p>Параметры не заданы.</p>:<div className="table-wrap"><table>
 <thead><tr><th>Параметр</th><th>Значение</th><th>Норма</th><th>Оценка</th></tr></thead><tbody>{component.specifications.map((spec,index)=>{
  const hasLimits=spec.minimum!=null||spec.maximum!=null;
  const outside=(spec.minimum!=null&&spec.value<spec.minimum)||(spec.maximum!=null&&spec.value>spec.maximum);
  return <tr key={`${spec.name}-${index}`}><td>{parameters[spec.name]||spec.name}</td><td>{number(spec.value)} {physicalUnits[spec.unit]||spec.unit}</td><td>{hasLimits?`${spec.minimum??"—"}…${spec.maximum??"—"} ${physicalUnits[spec.unit]||spec.unit}`:"Не задана"}</td><td>{outside?"⚠ Вне уставки":hasLimits?"В указанных пределах":"Нужен норматив"}</td></tr>;
 })}</tbody></table></div>}
 <h3>Нормативный ресурс</h3><p><strong>{statuses[resource.status]||resource.status}</strong></p>
 <div className="table-wrap"><table><thead><tr><th>Единица</th><th>Норматив</th><th>Использовано</th><th>Расчётный остаток</th></tr></thead><tbody>
 {Object.entries(resource.estimates).map(([unit,estimate])=><tr key={unit}><td>{units[unit]||unit}</td><td>{number(estimate.norm)}</td><td>{number(estimate.used)}</td><td>{number(estimate.remaining)}</td></tr>)}</tbody></table></div>
 <p>До регламентного ТО: <strong>{resource.service_remaining_hours==null?"Недостаточно данных":`${number(resource.service_remaining_hours)} ч`}</strong>{resource.service_due===true&&" · срок ТО наступил"}</p>
 <p className="notice">{resource.limitations}</p></>;
}

function WorkForm({component}:{component:EquipmentComponent}) {
 const repo=useRepository();const qc=useQueryClient();
 const [action,setAction]=useState<WorkAction>("INSPECTED");const [comment,setComment]=useState("");
 const [hours,setHours]=useState("");const [cycles,setCycles]=useState("");const [error,setError]=useState("");const [success,setSuccess]=useState("");const [busy,setBusy]=useState(false);
 const [pending,setPending]=useState<{signature:string;key:string;body:ComponentWorkInput}|null>(null);
 const inputCounters=action==="READINGS";
 return <form onSubmit={async event=>{
  event.preventDefault();setBusy(true);setError("");setSuccess("");
  const values={action,comment:comment.trim(),...(inputCounters&&hours!==""?{operating_hours:Number(hours)}:{}),...(inputCounters&&cycles!==""?{operating_cycles:Number(cycles)}:{})};
  const signature=JSON.stringify(values);
  const attempt=pending?.signature===signature?pending:{signature,key:requestKey(),body:{...values,occurred_at:new Date().toISOString(),expected_revision:component.revision}};
  setPending(attempt);
  try{
   await repo.recordWork(component.id,attempt.body,attempt.key);setPending(null);setComment("");setHours("");setCycles("");setSuccess("Работа сохранена в истории компонента.");
   await Promise.all([qc.invalidateQueries({queryKey:["equipment-card",component.equipment_id]}),qc.invalidateQueries({queryKey:["component-work",component.id]})]);
  }catch(error){setError(errorMessage(error));}finally{setBusy(false);}
 }}>
 <h3>Зарегистрировать работу</h3><p>Запись сохраняет автора, время, состояние до и после. Обслуживание само по себе не подтверждает устранение дефекта.</p>
 <label>Действие<select value={action} onChange={e=>setAction(e.target.value as WorkAction)} disabled={busy}>{Object.entries(workNames).map(([value,label])=><option value={value} key={value} disabled={(value==="STARTED"&&component.runtime_state==="RUNNING")||(value==="STOPPED"&&component.runtime_state!=="RUNNING")}>{label}</option>)}</select></label>
 {inputCounters&&<div className="grid"><label>Текущая наработка, ч<input type="number" min={0} max={1e9} step="any" value={hours} onChange={e=>setHours(e.target.value)} disabled={busy}/></label>
 <label>Текущие циклы<input type="number" min={0} max={2000000000} step={1} value={cycles} onChange={e=>setCycles(e.target.value)} disabled={busy}/></label></div>}
 {action==="REPLACED"&&<p className="notice">Замена обнулит наработку нового компонента. История прежнего компонента сохранится.</p>}
 {component.runtime_state==="RUNNING"&&<p className="notice">Перед обслуживанием, заменой или ручным вводом часов остановите счётчик.</p>}
 <label>Что проверено или выполнено<textarea value={comment} onChange={e=>setComment(e.target.value)} required minLength={1} maxLength={2000} disabled={busy} rows={3}/></label>
 {error&&<p role="alert" className="error">{error}</p>}{success&&<p role="status">{success}</p>}
 {error&&pending&&<p>Повтор без изменения полей отправит то же действие с тем же ключом, без второй записи.</p>}
 <button disabled={busy||!comment.trim()||(inputCounters&&hours===""&&cycles==="")}>{busy?"Сохраняем…":error&&pending?"Повторить сохранение":"Сохранить работу"}</button>
 {error&&<button type="button" className="secondary" disabled={busy} onClick={()=>{setPending(null);setComment("");setHours("");setCycles("");setError("");void Promise.all([qc.invalidateQueries({queryKey:["equipment-card",component.equipment_id]}),qc.invalidateQueries({queryKey:["component-work",component.id]})]);}}>Отменить ввод и обновить историю</button>}
 </form>;
}

function WorkHistory({component}:{component:EquipmentComponent}) {
 const repo=useRepository();const [offset,setOffset]=useState(0);
 const query=useQuery({queryKey:["component-work",component.id,offset],queryFn:()=>repo.componentWork(component.id,20,offset)});
 return <section><h3>История работ компонента</h3>{query.isPending?<p>Загрузка…</p>:query.isError?<p role="alert" className="error">{errorMessage(query.error)}</p>:
 <>{query.data.items.map(item=><article className="finding" key={item.work_id}><strong>{workNames[item.action]||item.action}</strong><p>{item.comment}</p><small>Выполнено: {time(item.occurred_at)} · Сохранено: {time(item.recorded_at)} · Автор №{item.author_id}</small></article>)}
 <Pagination offset={offset} total={query.data.total} onChange={setOffset} pending={query.isFetching}/></>}</section>;
}

const checkNames:Record<VisualCheck["code"],string>={SEAL_LEAK:"Влажное пятно или капли у уплотнения",FRAME_CORROSION:"Коррозия фундаментной рамы",LOOSE_ANCHOR:"Ослабление анкера",OIL_DARK:"Тёмное или мутное масло",OIL_LOW:"Масло ниже MIN",TERMINAL_OXIDATION:"Окисление или следы перегрева клемм",COUPLING_GUARD_MISSING:"Кожух муфты отсутствует или смещён"};

function DiagnosticPanel({card,component}:{card:EquipmentCard;component:EquipmentComponent}) {
 const repo=useRepository();const [loadDemo,setLoadDemo]=useState(false);const [scenario,setScenario]=useState("");
 const [manualChecks,setManualChecks]=useState<VisualCheck["code"][]>([]);const [result,setResult]=useState<DiagnosticPreview|null>(null);
 const [busy,setBusy]=useState(false);const [error,setError]=useState("");
 const demos=useQuery({queryKey:["demo-scenarios",card.id],queryFn:()=>repo.demoScenarios(card.id),enabled:loadDemo});
 const selected=demos.data?.scenarios.find(item=>item.name===scenario);
 const target=selected?demos.data!.component_id:component.id;
 const readings:SensorReading[]=selected?.telemetry||[];
 const checks:VisualCheck[]=selected?.visual_checks||manualChecks.map(code=>({code,observed:true,source:"MANUAL"}));
 return <section className="panel"><h2>Проверка логических связок</h2><p>Предварительная проверка по показаниям и ручным признакам. Этот экран не запускает нейросеть и не создаёт осмотр.</p>
 <button className="secondary" onClick={()=>loadDemo?void demos.refetch():setLoadDemo(true)} disabled={demos.isFetching}>{demos.isFetching?"Загрузка…":"Загрузить демонстрационные сценарии"}</button>
 {demos.isError&&<p role="alert" className="error">Демо-набор недоступен для этого оборудования: {errorMessage(demos.error)}</p>}
 {demos.data&&<><p className="notice">ДЕМО: синтетические показания. Это не данные реальных датчиков.</p><label>Сценарий<select value={scenario} onChange={event=>{setScenario(event.target.value);setResult(null);setError("");}}><option value="">Ручные визуальные замечания</option>{demos.data.scenarios.map(item=><option value={item.name} key={item.name}>{item.name}</option>)}</select></label></>}
 {selected?<><p>{selected.description}</p><p>Компонент сценария: {card.components.find(item=>item.id===target)?.name||`№${target}`}</p>
 <div className="table-wrap"><table><thead><tr><th>Параметр</th><th>Значение</th><th>Время</th><th>Источник</th></tr></thead><tbody>{readings.map((item,index)=><tr key={index}><td>{parameters[item.name]||item.name}</td><td>{number(item.value)} {physicalUnits[item.unit]||item.unit}</td><td>{time(item.measured_at)}</td><td>{item.source}</td></tr>)}</tbody></table></div>
 {checks.length>0&&<p>Ручные замечания сценария: {checks.filter(item=>item.observed).map(item=>checkNames[item.code]).join("; ")}</p>}</>:
 <fieldset><legend>Отметьте только то, что проверили визуально</legend>{Object.entries(checkNames).map(([code,label])=><label className="check" key={code}><input type="checkbox" checked={manualChecks.includes(code as VisualCheck["code"])} onChange={e=>{setResult(null);setManualChecks(e.target.checked?[...manualChecks,code as VisualCheck["code"]]:manualChecks.filter(item=>item!==code));}}/>{label}</label>)}</fieldset>}
 <div className="actions"><button disabled={busy} onClick={async()=>{setBusy(true);setError("");setResult(null);try{
  setResult(await repo.diagnosticPreview(card.id,{component_id:target,captured_at:selected?.captured_at||new Date().toISOString(),telemetry:readings,visual_checks:checks}));
 }catch(error){setError(errorMessage(error));}finally{setBusy(false);}}}>{busy?"Проверяем…":"Проверить связки"}</button></div>
 {error&&<p role="alert" className="error">{error}</p>}{result&&<div aria-live="polite"><Diagnostics items={result.diagnostics}/>{result.diagnostics.length===0&&<p>По переданным данным правила не сработали. Это не подтверждает исправность.</p>}
 {result.ignored_readings.length>0&&<p className="notice">Не использованы показания: {result.ignored_readings.join(", ")}. Проверьте единицы и время; повторно загрузите демо-сценарии, если они устарели.</p>}
 <p className="notice">{result.limitations}</p><button className="secondary" onClick={()=>void demos.refetch()} disabled={!loadDemo||demos.isFetching}>Обновить время демо-показаний</button></div>}
 </section>;
}

function InspectionHistory({equipmentId}:{equipmentId:number}) {
 const repo=useRepository();const [offset,setOffset]=useState(0);
 const query=useQuery({queryKey:["inspection-history",equipmentId,offset],queryFn:()=>repo.inspectionHistory(equipmentId,20,offset)});
 return <section className="panel"><h2>История осмотров</h2><button className="secondary" onClick={()=>void query.refetch()} disabled={query.isFetching}>Обновить историю</button>
 {query.isPending?<p>Загрузка…</p>:query.isError?<p role="alert" className="error">{errorMessage(query.error)}</p>:<>
 {query.data.items.map(item=><article className="finding" key={item.inspection_id}><h3>Осмотр №{item.inspection_id} · {time(item.created_at)}</h3>
 {item.result?<><strong>{statuses[item.result.status]||item.result.status}: {item.result.defect}</strong>
 <p>{item.result.reason}</p><p>{item.result.recommendation}</p>{item.result.comment&&<p>Комментарий: {item.result.comment}</p>}
 <p>Источник: {item.result.analysis_source==="MOCK"?"ДЕМО — синтетический осмотр":item.result.analysis_source}{item.result.analysis_location?` · ${item.result.analysis_location}`:""} · Проверка: {item.result.review_status}</p>
 {item.result.confidence!=null&&<p>Уверенность модели: {number(item.result.confidence*100)}%. Это не оценка тяжести.</p>}
 <Diagnostics items={item.result.diagnostics||[]}/>
 <div className="actions"><a className="button secondary" href={repo.inspectionExportUrl(item.inspection_id,"pdf")} download>Отчёт PDF</a><a className="button secondary" href={repo.inspectionExportUrl(item.inspection_id,"xlsx")} download>Отчёт Excel</a>
 {item.result.photo_id!=null&&<a className="button secondary" href={repo.inspectionPhotoUrl(item.result.photo_id)} target="_blank" rel="noreferrer">Снимок ↗</a>}</div></>:<p>{item.processing_status==="PROCESSING"?"Обработка не завершена":"Осмотр не завершён; отчёт недоступен"}</p>}</article>)}
 <Pagination offset={offset} total={query.data.total} onChange={setOffset} pending={query.isFetching}/></>}
 </section>;
}

function EquipmentMaintenance({id}:{id:number}) {
 const repo=useRepository();const [selected,setSelected]=useState<number|null>(null);
 const query=useQuery({queryKey:["equipment-card",id],queryFn:()=>repo.equipmentCard(id),refetchInterval:15000});
 if(query.isPending)return <section className="panel"><p>Загрузка карточки…</p></section>;
 if(query.isError)return <section className="panel"><p role="alert" className="error">{errorMessage(query.error)}</p><button onClick={()=>void query.refetch()}>Повторить</button></section>;
 const card=query.data;const component=card.components.find(item=>item.id===selected)||card.components[0];
 return <><section className="panel"><h2>{card.name}</h2><p>Инвентарный номер: <strong>{card.inventory_number}</strong></p><p>Заводской номер: <strong>{card.serial_number||"Не указан"}</strong></p><p className="passport">{card.passport}</p>
 <PassportFacts data_origin={card.data_origin} facts={card.facts}/>
 {component?<><label>Компонент<select value={component.id} onChange={e=>setSelected(Number(e.target.value))}>{card.components.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
 <ComponentCard component={component}/><WorkForm key={component.id} component={component}/><WorkHistory key={`history-${component.id}`} component={component}/></>:<p>Компоненты ещё не добавлены.</p>}</section>
 {component&&<DiagnosticPanel key={card.id} card={card} component={component}/>}
 <InspectionHistory equipmentId={id}/></>;
}

export function Maintenance() {
 const repo=useRepository();const [selected,setSelected]=useState<number|null>(null);
 const equipment=useQuery({queryKey:["equipment"],queryFn:()=>repo.list("equipment")});
 return <><section className="panel"><h2>Осмотры и обслуживание</h2><p>Выберите агрегат для просмотра ресурса, записи работ и выгрузки сохранённых осмотров.</p>
 {equipment.isPending?<p>Загрузка оборудования…</p>:equipment.isError?<p role="alert" className="error">{errorMessage(equipment.error)}</p>:equipment.data.length===0?<p>Оборудование ещё не добавлено.</p>:
 <label>Агрегат<select value={selected??""} onChange={event=>setSelected(event.target.value?Number(event.target.value):null)}><option value="">Выберите оборудование…</option>{equipment.data.map(item=><option key={String(item.id)} value={Number(item.id)}>{String(item.name)} · {String(item.inventory_number)}</option>)}</select></label>}</section>
 {selected!=null&&<EquipmentMaintenance key={selected} id={selected}/>}</>;
}
