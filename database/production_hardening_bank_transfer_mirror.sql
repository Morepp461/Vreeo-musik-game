-- Production hardening: keep wallet bank mirror synchronized with bank-account transfers.
create or replace function public.game_bank_transfer(p_from bigint,p_to bigint,p_amount bigint,p_reference text default null)
returns jsonb language plpgsql security definer set search_path=public as $function$
declare f game_bank_accounts; t game_bank_accounts; fw game_wallets; tw game_wallets;
begin
 if p_amount<=0 or p_from=p_to then raise exception 'Invalid transfer'; end if;
 select * into f from game_bank_accounts where id=p_from and status='active' for update;
 if not found then raise exception 'Account not found'; end if;
 select * into t from game_bank_accounts where id=p_to and status='active' for update;
 if not found then raise exception 'Account not found'; end if;
 if f.balance<p_amount then raise exception 'Insufficient balance'; end if;
 update game_bank_accounts set balance=balance-p_amount,updated_at=now() where id=f.id;
 update game_bank_accounts set balance=balance+p_amount,updated_at=now() where id=t.id;
 select * into fw from game_wallets where character_id=f.character_id for update;
 select * into tw from game_wallets where character_id=t.character_id for update;
 if not found then raise exception 'Wallet not found'; end if;
 update game_wallets set bank=greatest(0,bank-p_amount),updated_at=now() where id=fw.id;
 update game_wallets set bank=bank+p_amount,updated_at=now() where id=tw.id;
 insert into game_bank_transfers(from_account_id,to_account_id,amount,reference_key) values(f.id,t.id,p_amount,p_reference);
 return jsonb_build_object('from_balance',f.balance-p_amount,'to_balance',t.balance+p_amount);
end $function$;