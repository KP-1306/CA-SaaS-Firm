import type { Entity, Resource } from './types';
const apiBase='/api/v1';
const headers=()=>({'Content-Type':'application/json','X-Tenant-ID':localStorage.getItem('tenantId')??'11111111-1111-1111-1111-111111111111','X-Principal-ID':localStorage.getItem('principalId')??'22222222-2222-2222-2222-222222222222'});
export async function list(resource:Resource, search=''):Promise<Entity[]>{const r=await fetch(`${apiBase}/${resource}/?search=${encodeURIComponent(search)}`,{headers:headers()});if(!r.ok)throw new Error(await r.text());return r.json() as Promise<Entity[]>}
export async function save(resource:Resource, value:Record<string,unknown>):Promise<Entity>{const id=value.id;const r=await fetch(`${apiBase}/${resource}/${id?`${id}/`:''}`,{method:id?'PATCH':'POST',headers:headers(),body:JSON.stringify(value)});if(!r.ok)throw new Error(await r.text());return r.json() as Promise<Entity>}
