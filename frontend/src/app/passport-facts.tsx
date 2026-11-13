import type {PassportProvenance} from "../domain/models";

const origins:Record<string,string>={USER:"Введено пользователем",ORGANIZER_DOCUMENT:"Документы организаторов",ORGANIZER:"Материалы организаторов",ORGANIZERS:"Материалы организаторов",DEMO:"Демонстрационные данные"};

export function PassportFacts({data_origin,facts}:PassportProvenance) {
 return <details><summary><strong>Паспортные сведения</strong>{facts?.length?` · ${facts.length}`:""}</summary>
 <p>Происхождение: {data_origin?(origins[data_origin]||data_origin):"Не указано"}.</p>
 <p className="notice">Сведения из документов и карточки оборудования. Это не текущие показания датчиков.</p>
 {!facts?.length?<p>Паспортные факты с источниками не добавлены.</p>:<div className="table-wrap"><table>
 <thead><tr><th>Сведение</th><th>Значение</th><th>Источник и проверка</th></tr></thead>
 <tbody>{facts.map((fact,index)=>{
  const source=fact.source;
  const location=[source?.page!=null?`стр. ${source.page}`:null,source?.sheet?`лист ${source.sheet}`:null,source?.row!=null?`строка ${source.row}`:null,source?.cell?`ячейка ${source.cell}`:null].filter(Boolean).join(", ");
  return <tr key={`${fact.key}-${index}`}><td>{fact.name||fact.key}{fact.role&&<small> · {fact.role}</small>}</td>
   <td>{fact.value==null?"Не указано":typeof fact.value==="boolean"?fact.value?"Да":"Нет":String(fact.value)}{fact.value!=null&&fact.unit?` ${fact.unit}`:""}</td>
   <td>{source?.document_id!=null?<a href={`/industrial-vision/api/v1/source-documents/${encodeURIComponent(source.document_id)}/file`} target="_blank" rel="noopener noreferrer">{source.source_file||"Оригинал документа"}</a>:source?.source_file||"Источник не указан"}
   {location&&<div>{location}</div>}<div>Проверка: {source?.verification||"Не указана"}</div>
   {source?.excerpt&&<details><summary>Фрагмент документа</summary><p>{source.excerpt}</p></details>}</td></tr>;
 })}</tbody></table></div>}</details>;
}
