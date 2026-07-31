import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { list, save } from './api';
import type { Entity, Resource } from './types';
import { resourceLabels } from './types';
import { DEFAULT_BRAND_NAME } from '../../shared/brand';
import './master-data.css';

const resources=Object.keys(resourceLabels) as Resource[];
const defaults:Record<Resource,Record<string,unknown>>={firm:{name:'',legal_name:'',pan:'',gstin:'',email:'',mobile:'',address:'',status:'ACTIVE'},branches:{name:'',code:'',status:'ACTIVE'},teams:{name:'',code:'',status:'ACTIVE'},employees:{name:'',email:'',role:'STAFF',is_active:true},clients:{legal_name:'',trade_name:'',client_type:'PRIVATE_LIMITED',industry:'',pan:'',cin_or_llpin:'',registered_address:'',relationship_manager_id:'',engagement_status:'ACTIVE',notes:''},'client-contacts':{client_id:'',name:'',designation:'',email:'',mobile:'',is_primary:false,is_active:true},'client-gst-registrations':{client_id:'',gstin:'',state:'',trade_name:'',address:'',is_primary:false,is_active:true},'client-branches':{client_id:'',name:'',address:'',state:'',contact_name:'',contact_mobile:'',is_active:true},verticals:{name:'',code:'',status:'ACTIVE'},domains:{name:'',code:'',vertical_id:'',status:'ACTIVE'},services:{name:'',code:'',domain_id:'',status:'ACTIVE'}};

export function MasterDataApp(){
 const [resource,setResource]=useState<Resource>('clients'); const [rows,setRows]=useState<Entity[]>([]); const [search,setSearch]=useState(''); const [editing,setEditing]=useState<Record<string,unknown>|null>(null); const [error,setError]=useState('');
 const load=async()=>{try{setRows(await list(resource,search));setError('')}catch(e){setError(String(e))}};
 useEffect(()=>{void load()},[resource]);
 const fields=useMemo(()=>Object.keys(defaults[resource]),[resource]);
 const submit=async(e:FormEvent)=>{e.preventDefault();if(!editing)return;try{await save(resource,editing);setEditing(null);await load()}catch(err){setError(String(err))}};
 return <div className="md-shell"><aside><h1>{DEFAULT_BRAND_NAME}</h1><p>Master Data</p>{resources.map(r=><button className={r===resource?'active':''} onClick={()=>{setResource(r);setEditing(null)}} key={r}>{resourceLabels[r]}</button>)}</aside><main><header><div><h2>{resourceLabels[resource]}</h2><small>Layer 2 configuration</small></div><button onClick={()=>setEditing({...defaults[resource]})}>Add new</button></header><div className="toolbar"><input placeholder="Search" value={search} onChange={e=>setSearch(e.target.value)}/><button onClick={()=>void load()}>Search</button></div>{error&&<p className="error">{error}</p>}<table><thead><tr><th>Name</th><th>Status / Role</th><th></th></tr></thead><tbody>{rows.map(row=><tr key={row.id}><td>{String(row.legal_name??row.name??row.email??row.id)}</td><td>{String(row.status??row.engagement_status??row.role??(row.is_active?'Active':'Inactive')??'')}</td><td><button onClick={()=>setEditing({...row})}>Edit</button></td></tr>)}</tbody></table>{editing&&<div className="modal"><form onSubmit={submit}><h3>{editing.id?'Edit':'Add'} {resourceLabels[resource]}</h3>{fields.map(field=><label key={field}>{field.replaceAll('_',' ')}<input value={String(editing[field]??'')} onChange={e=>setEditing({...editing,[field]:e.target.value})}/></label>)}<div><button type="button" onClick={()=>setEditing(null)}>Cancel</button><button type="submit">Save</button></div></form></div>}</main></div>
}
