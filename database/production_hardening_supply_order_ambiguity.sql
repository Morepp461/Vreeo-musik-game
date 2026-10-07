-- Production hardening: qualify business.id to avoid PL/pgSQL variable ambiguity.
create or replace function public.game_create_supply_order(p_supplier bigint, p_buyer bigint, p_item_key text, p_quantity bigint, p_unit_price bigint)
returns bigint
language plpgsql
security definer
set search_path = public
as $function$
declare
  v_id bigint;
begin
  if p_quantity<=0 or p_unit_price<0 or p_supplier=p_buyer then
    raise exception 'Invalid supply order';
  end if;

  if not exists(
    select 1 from public.game_businesses b
    where b.id=p_supplier and b.status='active'
  ) or not exists(
    select 1 from public.game_businesses b
    where b.id=p_buyer and b.status='active'
  ) then
    raise exception 'Business not active';
  end if;

  insert into public.game_supply_chain(
    supplier_business_id,buyer_business_id,item_key,quantity,unit_price
  )
  values(p_supplier,p_buyer,p_item_key,p_quantity,p_unit_price)
  returning game_supply_chain.id into v_id;

  return v_id;
end
$function$;
