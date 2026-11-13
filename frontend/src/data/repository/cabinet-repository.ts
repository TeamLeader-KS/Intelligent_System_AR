import type {CabinetRepository} from "../../domain/repository";
import type {Account,Key,Resource,Row,AndroidBuild,EquipmentCard,Page,ComponentWork,ComponentWorkInput,InspectionHistoryItem,DemoScenarios,DiagnosticPreview,SensorReading,VisualCheck,DemoPump} from "../../domain/models";
import {api} from "../http";
export class HttpCabinetRepository implements CabinetRepository {
  androidBuild(){return api<AndroidBuild>("android-build");}
  demoPumps(){return api<{items:DemoPump[]}>("demo-pumps");}
  currentAdmin(){return api<Account>("auth/me");}
  login(data:Record<string,FormDataEntryValue>){return api<Account>("auth/login","POST",data);}
  logout(){return api<void>("auth/logout","POST");}
  keys(){return api<Key[]>("keys");}
  issueKey(data:{name:string;days:number}){return api<{key:string}>("keys","POST",data);}
  revokeKey(id:number){return api<void>("keys/"+id,"DELETE");}
  list(resource:Resource){return api<Row[]>(resource);}
  create(resource:Resource,data:unknown){return api<{id:number}>(resource,"POST",data);}
  equipmentCard(id:number){return api<EquipmentCard>(`equipment/${id}/card`);}
  inspectionHistory(id:number,limit:number,offset:number){return api<Page<InspectionHistoryItem>>(`equipment/${id}/inspections?limit=${limit}&offset=${offset}`);}
  componentWork(id:number,limit:number,offset:number){return api<Page<ComponentWork>>(`components/${id}/work?limit=${limit}&offset=${offset}`);}
  recordWork(id:number,data:ComponentWorkInput,key:string){return api<ComponentWork>(`components/${id}/work`,"POST",data,{"Idempotency-Key":key});}
  demoScenarios(id:number){return api<DemoScenarios>(`equipment/${id}/demo-scenarios`);}
  diagnosticPreview(id:number,data:{component_id:number;captured_at:string;telemetry:SensorReading[];visual_checks:VisualCheck[]}){return api<DiagnosticPreview>(`equipment/${id}/diagnostics/preview`,"POST",data);}
  inspectionExportUrl(id:number,format:"pdf"|"xlsx"){return `/industrial-vision/api/v1/inspections/${id}/export?format=${format}`;}
  inspectionPhotoUrl(id:number){return `/industrial-vision/api/v1/photos/${id}`;}
}
