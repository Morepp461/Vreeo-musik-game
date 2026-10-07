create or replace function public.game_apply_for_job(p_character_id bigint,p_job_key text)
returns jsonb language plpgsql security definer set search_path=public as $$
declare j game_jobs%rowtype; c game_characters%rowtype; inst game_institutions%rowtype; s integer; types jsonb;
begin
 select * into c from game_characters where id=p_character_id for update;
 if not found then raise exception 'CHARACTER_NOT_FOUND'; end if;
 select * into j from game_jobs where job_key=p_job_key and active=true;
 if not found then raise exception 'JOB_NOT_FOUND'; end if;
 if c.status<>'active' then raise exception 'CHARACTER_NOT_ACTIVE'; end if;
 if exists(select 1 from game_character_jobs where character_id=p_character_id and status='active') then raise exception 'ALREADY_EMPLOYED'; end if;
 select coalesce(max(level),0) into s from game_character_skills where character_id=p_character_id;
 if s<j.min_skill then raise exception 'SKILL_TOO_LOW'; end if;
 types=coalesce(j.metadata->'workplace_types','["company"]'::jsonb);
 select * into inst from game_institutions
 where status='open' and city_id=(select id from game_cities where lower(name)=lower(c.city) limit 1)
 and institution_type in (select jsonb_array_elements_text(types))
 order by case when institution_type='company' then 0 else 1 end,id limit 1;
 insert into game_character_jobs(character_id,job_id,salary,skill,employer_institution_id)
 values(p_character_id,j.id,j.base_salary,0,inst.id);
 return jsonb_build_object('success',true,'job_name',j.job_name,'salary',j.base_salary,'skill',0,
   'workplace_id',inst.id,'workplace_name',inst.name,'workplace_type',inst.institution_type);
exception when no_data_found then
 insert into game_character_jobs(character_id,job_id,salary,skill)
 values(p_character_id,j.id,j.base_salary,0);
 return jsonb_build_object('success',true,'job_name',j.job_name,'salary',j.base_salary,'skill',0,'workplace_name','Menunggu penempatan');
end $$;

create or replace function public.game_payroll_period(p_period_key text)
returns jsonb language plpgsql security definer set search_path=public as $$
declare r record; paid bigint:=0; cnt integer:=0;
begin
 if p_period_key is null or length(trim(p_period_key))=0 then raise exception 'INVALID_PERIOD'; end if;
 for r in
   select cj.id,cj.character_id,cj.salary from game_character_jobs cj
   join game_characters c on c.id=cj.character_id
   where cj.status='active' and c.status='active' and cj.employer_business_id is null
   for update of cj
 loop
   insert into game_job_payments(character_job_id,period_key,amount)
   values(r.id,p_period_key,r.salary) on conflict(character_job_id,period_key) do nothing;
   if found then
     perform game_wallet_adjust(r.character_id,'cash',r.salary,'salary','Payroll '+p_period_key,'payroll:'+r.id::text+':'+p_period_key);
     paid=paid+r.salary; cnt=cnt+1;
   end if;
 end loop;
 return jsonb_build_object('success',true,'employees_paid',cnt,'total_paid',paid,'period_key',p_period_key);
end $$;

revoke all on function public.game_apply_for_job(bigint,text) from public,anon,authenticated;
revoke all on function public.game_payroll_period(text) from public,anon,authenticated;
grant execute on function public.game_apply_for_job(bigint,text) to service_role;
grant execute on function public.game_payroll_period(text) to service_role;
