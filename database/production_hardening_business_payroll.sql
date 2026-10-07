-- Production hardening: business payroll must target the employee wallet row.
create or replace function public.game_close_business_finance(p_period_key text)
returns jsonb language plpgsql security definer set search_path=public as $function$
declare b record; emp record; rev bigint; payroll bigint; op bigint; tax bigint; loan bigint; profit bigint; paid int:=0; closed int:=0; wallet_id bigint;
begin
 for b in select * from game_businesses where status='active' for update loop
  if exists(select 1 from game_business_finance_periods where business_id=b.id and period_key=p_period_key) then continue; end if;
  select coalesce(sum(case when transaction_type in ('sale','revenue','income') and amount>0 then amount else 0 end),0),coalesce(sum(case when transaction_type not in ('sale','revenue','income') and amount<0 then -amount else 0 end),0) into rev,op from game_business_transactions where business_id=b.id and created_at>=date_trunc('month',now());
  payroll:=0;
  for emp in select character_id,salary from game_business_employees where business_id=b.id and status='active' loop
   if b.cash>=emp.salary then
    select id into wallet_id from game_wallets where character_id=emp.character_id;
    if wallet_id is null then raise exception 'WALLET_NOT_FOUND'; end if;
    perform game_wallet_adjust(wallet_id,'cash',emp.salary,'business_payroll','Gaji dari '||b.name,'business-payroll:'||b.id||':'||p_period_key||':'||emp.character_id);
    b.cash:=b.cash-emp.salary; payroll:=payroll+emp.salary; paid:=paid+1;
   end if;
  end loop;
  tax:=greatest(0,round((rev-op-payroll)*0.02));
  if b.cash>=tax then b.cash:=b.cash-tax; else tax:=0; end if;
  loan:=least(b.loan_principal,greatest(0,round(b.loan_principal*0.02)));
  if b.cash>=loan then b.cash:=b.cash-loan; b.loan_principal:=b.loan_principal-loan; end if;
  profit:=rev-op-payroll-tax-loan;
  update game_businesses set cash=b.cash,monthly_revenue=rev,monthly_expense=op+payroll+tax+loan,monthly_profit=profit,last_payroll_period=p_period_key,status=case when b.cash<=0 and profit<0 then 'insolvent' else status end where id=b.id;
  insert into game_business_finance_periods(business_id,period_key,revenue,payroll_expense,operating_expense,loan_payment,tax_expense,net_profit,closing_cash) values(b.id,p_period_key,rev,payroll,op,loan,tax,profit,b.cash);
  closed:=closed+1;
 end loop;
 return jsonb_build_object('success',true,'period_key',p_period_key,'businesses_closed',closed,'employees_paid',paid);
end $function$;