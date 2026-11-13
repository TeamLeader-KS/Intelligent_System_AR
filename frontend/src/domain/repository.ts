import type {Account,Key,Resource,Row,AndroidBuild,EquipmentCard,Page,ComponentWork,ComponentWorkInput,InspectionHistoryItem,DemoScenarios,DiagnosticPreview,SensorReading,VisualCheck} from "./models";
export interface CabinetRepository {
  androidBuild():Promise<AndroidBuild>;
  currentAdmin():Promise<Account>;
  login(data:Record<string,FormDataEntryValue>):Promise<Account>;
  logout():Promise<void>;
  keys():Promise<Key[]>;
  issueKey(data:{name:string;days:number}):Promise<{key:string}>;
  revokeKey(id:number):Promise<void>;
  list(resource:Resource):Promise<Row[]>;
  create(resource:Resource, data:unknown):Promise<{id:number}>;
  equipmentCard(id:number):Promise<EquipmentCard>;
  inspectionHistory(id:number,limit:number,offset:number):Promise<Page<InspectionHistoryItem>>;
  componentWork(id:number,limit:number,offset:number):Promise<Page<ComponentWork>>;
  recordWork(id:number,data:ComponentWorkInput,key:string):Promise<ComponentWork>;
  demoScenarios(id:number):Promise<DemoScenarios>;
  diagnosticPreview(id:number,data:{component_id:number;captured_at:string;telemetry:SensorReading[];visual_checks:VisualCheck[]}):Promise<DiagnosticPreview>;
  inspectionExportUrl(id:number,format:"pdf"|"xlsx"):string;
  inspectionPhotoUrl(id:number):string;
}
