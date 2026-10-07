-- Production hardening: canonical cities, banking lifecycle, supply validation and payroll floors.
update public.game_ai_characters
set city=case city
  when 'Banjarmasin' then 'Balikpapan'
  when 'Padang' then 'Pekanbaru'
  when 'Manado' then 'Makassar'
  when 'Samarinda' then 'Balikpapan'
  when 'Pontianak' then 'Balikpapan'
  when 'Mataram' then 'Denpasar'
  when 'Solo' then 'Yogyakarta'
  when 'Bogor' then 'Jakarta'
  else city end
where alive=true and city not in (select name from public.game_cities where active=true);

create unique index if not exists game_bank_accounts_one_active_character_idx
on public.game_bank_accounts(character_id) where status='active';

create or replace function public.game_travel(p_character_id bigint,p_destination text)
returns jsonb language plpgsql security definer set search_path=public as $function$
declare c public.game_characters%rowtype; n public.game_needs%rowtype; w public.game_wallets%rowtype; destrow public.game_cities%rowtype; travel_cost bigint:=75000; new_cash bigint; dest text;
begin
 dest:=trim(p_destination);
 select * into destrow from public.game_cities where active and name=dest limit 1;
 if not found then raise exception 'DESTINATION_NOT_AVAILABLE'; end if;
 select * into c from public.game_characters where id=p_character_id for update;
 if not found then raise exception 'CHARACTER_NOT_FOUND'; end if;
 if c.status<>'active' then raise exception 'CHARACTER_NOT_ACTIVE'; end if;
 select * into n from public.game_needs where character_id=p_character_id for update;
 select * into w from public.game_wallets where character_id=p_character_id for update;
 if w.cash<travel_cost then raise exception 'INSUFFICIENT_CASH'; end if;
 if n.energy<15 then raise exception 'NOT_ENOUGH_ENERGY'; end if;
 new_cash:=w.cash-travel_cost;
 update public.game_wallets set cash=new_cash,updated_at=now() where id=w.id;
 update public.game_characters set city=destrow.name,province=(select r.name from public.game_regions r where r.id=destrow.region_id),updated_at=now() where id=p_character_id;
 update public.game_needs set energy=greatest(0,energy-15),hunger=greatest(0,hunger-5),thirst=greatest(0,thirst-5),stress=greatest(0,stress-3),updated_at=now() where character_id=p_character_id;
 insert into public.game_transactions(wallet_id,account_type,amount,balance_after,transaction_type,description,reference_key) values(w.id,'cash',-travel_cost,new_cash,'travel','Perjalanan ke '||destrow.name,'travel:'||lower(destrow.name));
 insert into public.game_action_log(character_id,action_key,action_name,outcome,money_delta,energy_delta,hunger_delta,thirst_delta,stress_delta,metadata) values(p_character_id,'travel','Perjalanan','Kamu bepergian ke '||destrow.name||'.',-travel_cost,-15,-5,-5,-3,jsonb_build_object('destination',destrow.name,'region_id',destrow.region_id));
 return jsonb_build_object('success',true,'destination',destrow.name,'province',(select r.name from public.game_regions r where r.id=destrow.region_id),'cash',new_cash);
end $function$;

create or replace function public.game_create_supply_order(p_supplier bigint,p_buyer bigint,p_item_key text,p_quantity bigint,p_unit_price bigint)
returns bigint language plpgsql security definer set search_path=public as $function$
declare v_id bigint;
begin
 if p_quantity<=0 or p_unit_price<=0 or p_supplier=p_buyer then raise exception 'Invalid supply order'; end if;
 if not exists(select 1 from public.game_market where item_key=p_item_key and active=true) then raise exception 'Item not found'; end if;
 if not exists(select 1 from public.game_businesses b where b.id=p_supplier and b.status='active' and b.legal_status='legal')
    or not exists(select 1 from public.game_businesses b where b.id=p_buyer and b.status='active' and b.legal_status='legal') then raise exception 'Business not active'; end if;
 insert into public.game_supply_chain(supplier_business_id,buyer_business_id,item_key,quantity,unit_price)
 values(p_supplier,p_buyer,p_item_key,p_quantity,p_unit_price)
 returning game_supply_chain.id into v_id;
 return v_id;
end $function$;

create or replace function public.game_hire_employee(p_business_id bigint,p_owner_character_id bigint,p_character_id bigint,p_role_title text,p_salary bigint)
returns jsonb language plpgsql security definer set search_path=public as $function$
declare b game_businesses%rowtype; minw bigint;
begin
 select * into b from game_businesses where id=p_business_id and status='active' for update;
 if not found or b.owner_character_id<>p_owner_character_id then raise exception 'NOT_BUSINESS_OWNER'; end if;
 select coalesce(c.minimum_wage_idr,0) into minw from game_cities c where c.id=b.city_id;
 if p_salary<greatest(0,minw) then raise exception 'SALARY_BELOW_MINIMUM_WAGE'; end if;
 if exists(select 1 from game_business_employees where business_id=b.id and character_id=p_character_id and status='active') then raise exception 'ALREADY_EMPLOYEE'; end if;
 insert into game_business_employees(business_id,character_id,role_title,salary,status) values(b.id,p_character_id,p_role_title,p_salary,'active');
 return jsonb_build_object('success',true);
end $function$;

create or replace function public.game_hire_employee_v2(p_business_id bigint,p_owner_character_id bigint,p_character_id bigint,p_job_key text,p_salary bigint)
returns jsonb language plpgsql security definer set search_path=public as $function$
declare b game_businesses%rowtype; j game_jobs%rowtype; c game_characters%rowtype; emp_id bigint; minw bigint;
begin
 select * into b from game_businesses where id=p_business_id and status='active' for update;
 if not found or b.owner_character_id<>p_owner_character_id then raise exception 'NOT_BUSINESS_OWNER'; end if;
 select * into c from game_characters where id=p_character_id and status='active' for update;
 if not found then raise exception 'CHARACTER_NOT_ACTIVE'; end if;
 select * into j from game_jobs where job_key=p_job_key and active=true;
 if not found then raise exception 'JOB_NOT_FOUND'; end if;
 select coalesce(ci.minimum_wage_idr,0) into minw from game_cities ci where ci.id=b.city_id;
 if p_salary<greatest(0,minw) then raise exception 'SALARY_BELOW_MINIMUM_WAGE'; end if;
 if exists(select 1 from game_business_employees where business_id=b.id and character_id=p_character_id and status='active') then raise exception 'ALREADY_EMPLOYEE'; end if;
 if exists(select 1 from game_character_jobs where character_id=p_character_id and status='active') then raise exception 'ALREADY_EMPLOYED'; end if;
 insert into game_business_employees(business_id,character_id,role_title,salary,status) values(b.id,c.id,j.job_name,p_salary,'active') returning id into emp_id;
 insert into game_character_jobs(character_id,job_id,status,salary,skill,employer_business_id) values(c.id,j.id,'active',p_salary,0,b.id);
 return jsonb_build_object('success',true,'employee_id',emp_id,'job_name',j.job_name,'salary',p_salary,'business_id',b.id);
end $function$;

create or replace function public.game_run_bank_loan_tick(p_tick_key text)
returns jsonb language plpgsql security definer set search_path=public as $function$
declare l record; checked int:=0; overdue int:=0; defaulted int:=0; key text:=trim(p_tick_key);
begin
 if key is null or length(key)=0 then raise exception 'INVALID_TICK_KEY'; end if;
 if exists(select 1 from public.game_government_ticks where tick_key='loan:'||key) then return jsonb_build_object('success',true,'already_processed',true,'tick_key',key); end if;
 for l in select bl.id,bl.character_id,bl.account_id,bl.outstanding_principal,bl.installment,bl.annual_interest_rate,bl.next_due_at,coalesce(ba.balance,0) balance from public.game_bank_loans bl left join public.game_bank_accounts ba on ba.id=bl.account_id and ba.status='active' where bl.status='active' for update of bl loop
  checked:=checked+1;
  if l.next_due_at is not null and l.next_due_at<=now() then
   overdue:=overdue+1;
   if l.balance>=least(l.installment,l.outstanding_principal+ceil(l.outstanding_principal*l.annual_interest_rate/12)) then perform public.game_repay_bank_loan(l.id,null);
   else
    update public.game_bank_loans set status='defaulted',closed_at=now() where id=l.id;
    insert into public.game_credit_history(character_id,loan_id,event_type,amount,score_delta,metadata) values(l.character_id,l.id,'loan_default',l.outstanding_principal,-80,jsonb_build_object('defaulted_at',now()));
    update public.game_wallets set debt=greatest(debt,l.outstanding_principal) where character_id=l.character_id;
    defaulted:=defaulted+1;
   end if;
  end if;
 end loop;
 insert into public.game_government_ticks(tick_key,policies_applied,elections_started,elections_completed,approval_changes,notes) values('loan:'||key,0,0,0,0,format('bank loan tick: checked=%s overdue=%s defaulted=%s',checked,overdue,defaulted));
 return jsonb_build_object('success',true,'already_processed',false,'tick_key',key,'checked',checked,'overdue',overdue,'defaulted',defaulted);
end $function$;
revoke all on function public.game_run_bank_loan_tick(text) from public,anon,authenticated;
grant execute on function public.game_run_bank_loan_tick(text) to service_role;