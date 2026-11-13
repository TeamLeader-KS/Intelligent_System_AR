import type {CabinetRepository} from "../../domain/repository";
import type {Account,Key,Resource,Row,AndroidBuild} from "../../domain/models";
import {api} from "../http";
export class HttpCabinetRepository implements CabinetRepository {
  androidBuild(){return api<AndroidBuild>("android-build");}
  currentAdmin(){return api<Account>("auth/me");}
  login(data:Record<string,FormDataEntryValue>){return api<Account>("auth/login","POST",data);}
  logout(){return api<void>("auth/logout","POST");}
  keys(){return api<Key[]>("keys");}
  issueKey(data:{name:string;days:number}){return api<{key:string}>("keys","POST",data);}
  revokeKey(id:number){return api<void>("keys/"+id,"DELETE");}
  list(resource:Resource){return api<Row[]>(resource);}
  create(resource:Resource,data:unknown){return api<{id:number}>(resource,"POST",data);}
}
