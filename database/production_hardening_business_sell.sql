-- Production hardening: repair business sale expression and reject zero-price sales.
create or replace function public.game_business_sell(p_business_id bigint,p_character_id bigint,p_item_key text,p_quantity bigint,p_unit_price bigint)
returns jsonb language plpgsql security definer set search_path=public as $function$
declare b game_businesses%rowtype; i game_business_inventory%rowtype; total bigint; new_cash bigint;
begin
 select * into b from game_businesses where id=p_business_id and status='active' for update;
 if not found or b.owner_character_id<>p_character_id then raise exception 'NOT_BUSINESS_OWNER'; end if;
 if p_quantity<=0 or p_unit_price<=0 then raise exception 'INVALID_SALE'; end if;
 select * into i from game_business_inventory where business_id=p_business_id and item_key=p_item_key for update;
 if not found or i.quantity<p_quantity then raise exception 'INSUFFICIENT_STOCK'; end if;
 total=p_quantity*p_unit_price; new_cash=b.cash+total;
 update game_business_inventory set quantity=quantity-p_quantity,updated_at=now() where id=i.id;
 update game_businesses set cash=new_cash,reputation=least(100,reputation+1) where id=b.id;
 insert into game_business_transactions(business_id,amount,transaction_type,description,reference_key) values(b.id,total,'sale','Penjualan '||i.item_name,'sale:'||b.id||':'||extract(epoch from clock_timestamp())::bigint);
 return jsonb_build_object('success',true,'total',total,'cash',new_cash);
end $function$;