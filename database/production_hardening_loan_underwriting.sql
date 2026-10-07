-- Production hardening: loan underwriting includes active exposure and loan-count limits.
create or replace function public.game_apply_bank_loan(p_character_id bigint,p_amount bigint,p_term_months integer default 12)
returns jsonb language plpgsql security definer set search_path=public as $function$
declare w game_wallets; a game_bank_accounts; score integer; rate numeric; inst bigint; l game_bank_loans; monthly_income bigint; exposure bigint; max_exposure bigint;
begin
 if p_amount<=0 or p_term_months<1 or p_term_months>120 then raise exception 'Invalid loan'; end if;
 select * into w from game_wallets where character_id=p_character_id for update;
 if not found then raise exception 'Wallet not found'; end if;
 select * into a from game_bank_accounts where character_id=p_character_id and status='active' limit 1;
 if not found then raise exception 'Active bank account required'; end if;
 select greatest(300,least(850,600+coalesce(sum(score_delta),0))) into score from game_credit_history where character_id=p_character_id;
 if score<500 then
  insert into game_credit_history(character_id,event_type,amount,score_delta,metadata) values(p_character_id,'loan_rejected',p_amount,0,jsonb_build_object('reason','credit_score'));
  return jsonb_build_object('status','rejected','credit_score',score);
 end if;
 select coalesce(sum(cj.salary),0)::bigint into monthly_income from game_character_jobs cj where cj.character_id=p_character_id and cj.status='active';
 select coalesce(sum(outstanding_principal),0)::bigint into exposure from game_bank_loans where character_id=p_character_id and status='active';
 max_exposure:=greatest(500000,monthly_income*6+(w.cash+w.bank)*2);
 if (select count(*) from game_bank_loans where character_id=p_character_id and status='active')>=3 or exposure+p_amount>max_exposure then
  insert into game_credit_history(character_id,event_type,amount,score_delta,metadata) values(p_character_id,'loan_rejected',p_amount,0,jsonb_build_object('reason','exposure_limit','max_exposure',max_exposure,'existing_exposure',exposure));
  return jsonb_build_object('status','rejected','credit_score',score,'reason','exposure_limit','max_exposure',max_exposure);
 end if;
 rate=greatest(0.06,0.12-(score-600)*0.0001);
 inst=ceil((p_amount*(1+rate*(p_term_months::numeric/12)))/p_term_months);
 insert into game_bank_loans(character_id,account_id,principal,outstanding_principal,annual_interest_rate,term_months,installment,credit_score,next_due_at)
 values(p_character_id,a.id,p_amount,p_amount,rate,p_term_months,inst,score,now()+interval '1 month') returning * into l;
 update game_wallets set bank=bank+p_amount,debt=debt+p_amount,updated_at=now() where id=w.id;
 update game_bank_accounts set balance=balance+p_amount,updated_at=now() where id=a.id;
 insert into game_credit_history(character_id,loan_id,event_type,amount,score_delta) values(p_character_id,l.id,'loan_approved',p_amount,-5);
 return jsonb_build_object('status','approved','loan_id',l.id,'credit_score',score,'annual_rate',rate,'installment',inst,'max_exposure',max_exposure);
end $function$;