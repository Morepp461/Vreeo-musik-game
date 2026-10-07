-- Production hardening: game_businesses has no updated_at column.
create or replace function public.game_fulfill_supply_order(p_order_id bigint)
returns jsonb
language plpgsql
security definer
set search_path = public
as $function$
declare
  o game_supply_chain;
  s game_business_inventory;
  b game_businesses;
  supplier game_businesses;
  total bigint;
begin
  select * into o from game_supply_chain
  where id=p_order_id and status='pending'
  for update;
  if not found then raise exception 'Supply order not found'; end if;

  total=o.quantity*o.unit_price;
  if total <= 0 then raise exception 'Invalid supply order total'; end if;

  select * into s from game_business_inventory
  where business_id=o.supplier_business_id and item_key=o.item_key
  for update;
  if not found or s.quantity<o.quantity then raise exception 'Supplier stock insufficient'; end if;

  select * into b from game_businesses where id=o.buyer_business_id for update;
  if not found or b.cash<total then raise exception 'Buyer cash insufficient'; end if;

  select * into supplier from game_businesses where id=o.supplier_business_id for update;
  if not found then raise exception 'Supplier business not found'; end if;

  update game_business_inventory set quantity=quantity-o.quantity,updated_at=now() where id=s.id;

  insert into game_business_inventory(
    business_id,item_key,item_name,quantity,unit_cost,sell_price
  )
  select b.id,m.item_key,m.item_name,o.quantity,o.unit_price,m.price
  from game_market m where m.item_key=o.item_key
  on conflict(business_id,item_key) do update
    set quantity=game_business_inventory.quantity+excluded.quantity,
        unit_cost=excluded.unit_cost,updated_at=now();

  update game_businesses set cash=cash-total where id=b.id;
  update game_businesses set cash=cash+total where id=supplier.id;

  update game_supply_chain set status='fulfilled',fulfilled_at=now() where id=o.id;

  insert into game_business_transactions(
    business_id,amount,transaction_type,description,reference_key
  )
  values
    (o.buyer_business_id,-total,'supply_purchase','Supply chain purchase','supply:'||o.id),
    (o.supplier_business_id,total,'supply_sale','Supply chain sale','supply:'||o.id);

  return jsonb_build_object('order_id',o.id,'total',total,'status','fulfilled');
end
$function$;
