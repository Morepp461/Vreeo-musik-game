update public.game_cities set
geography=case city_key
 when 'jakarta' then '{"terrain":"metropolitan coastal plain","role":"national capital region"}'::jsonb
 when 'bandung' then '{"terrain":"highland basin","role":"West Java urban-industrial and education center"}'::jsonb
 when 'semarang' then '{"terrain":"north-coast plain and southern hills","role":"Central Java trade and port center"}'::jsonb
 when 'yogyakarta' then '{"terrain":"urban basin near Merapi","role":"education, culture and tourism center"}'::jsonb
 when 'surabaya' then '{"terrain":"north-coast lowland","role":"East Java trade, port and industrial center"}'::jsonb
 when 'malang' then '{"terrain":"highland","role":"education, services and tourism center"}'::jsonb
 when 'tangerang' then '{"terrain":"Banten urban-industrial plain","role":"Jakarta metropolitan industrial/service corridor"}'::jsonb
 when 'medan' then '{"terrain":"northeast Sumatra lowland","role":"North Sumatra metropolitan and trade center"}'::jsonb
 when 'palembang' then '{"terrain":"Musi river lowland","role":"South Sumatra trade and service center"}'::jsonb
 when 'pekanbaru' then '{"terrain":"central Sumatra lowland","role":"Riau administrative and service center"}'::jsonb
 when 'denpasar' then '{"terrain":"southern Bali urban corridor","role":"Bali tourism and service center"}'::jsonb
 when 'balikpapan' then '{"terrain":"coastal hilly terrain","role":"East Kalimantan energy, logistics and service center"}'::jsonb
 when 'makassar' then '{"terrain":"southwest Sulawesi coastal plain","role":"eastern Indonesia trade and logistics hub"}'::jsonb
 when 'jayapura' then '{"terrain":"coastal hills and bays","role":"Papua government and service center"}'::jsonb else geography end,
economy_profile=case city_key
 when 'jakarta' then '{"dominant":["finance","business_services","government","trade","information_communication"]}'::jsonb
 when 'bandung' then '{"dominant":["manufacturing","creative_economy","trade","education","services"]}'::jsonb
 when 'semarang' then '{"dominant":["manufacturing","trade","logistics","port_services","services"]}'::jsonb
 when 'yogyakarta' then '{"dominant":["education","tourism","creative_economy","services"]}'::jsonb
 when 'surabaya' then '{"dominant":["manufacturing","trade","logistics","port_services","services"]}'::jsonb
 when 'malang' then '{"dominant":["education","services","tourism","trade","manufacturing"]}'::jsonb
 when 'tangerang' then '{"dominant":["manufacturing","logistics","trade","services"]}'::jsonb
 when 'medan' then '{"dominant":["trade","services","manufacturing","logistics","agriculture_hinterland"]}'::jsonb
 when 'palembang' then '{"dominant":["trade","services","manufacturing","energy_hinterland","logistics"]}'::jsonb
 when 'pekanbaru' then '{"dominant":["trade","construction","processing","services","energy_hinterland"]}'::jsonb
 when 'denpasar' then '{"dominant":["tourism","trade","accommodation","food_services","creative_economy"]}'::jsonb
 when 'balikpapan' then '{"dominant":["energy_services","logistics","construction","trade","services"]}'::jsonb
 when 'makassar' then '{"dominant":["trade","logistics","manufacturing","construction","services"]}'::jsonb
 when 'jayapura' then '{"dominant":["government","services","trade","construction","logistics"]}'::jsonb else economy_profile end,
human_resources=case city_key
 when 'jakarta' then '{"profile":"large metropolitan skilled-service labor market"}'::jsonb
 when 'bandung' then '{"profile":"large urban labor market with education and creative talent"}'::jsonb
 when 'semarang' then '{"profile":"urban industrial and logistics workforce"}'::jsonb
 when 'yogyakarta' then '{"profile":"student, education and creative workforce"}'::jsonb
 when 'surabaya' then '{"profile":"large industrial, logistics and service workforce"}'::jsonb
 when 'malang' then '{"profile":"student, education, service and tourism workforce"}'::jsonb
 when 'tangerang' then '{"profile":"large metropolitan manufacturing and service workforce"}'::jsonb
 when 'medan' then '{"profile":"large metropolitan trade and service workforce"}'::jsonb
 when 'palembang' then '{"profile":"trade, services and industrial workforce"}'::jsonb
 when 'pekanbaru' then '{"profile":"service and administrative workforce with regional energy-linked economy"}'::jsonb
 when 'denpasar' then '{"profile":"tourism, hospitality and service workforce"}'::jsonb
 when 'balikpapan' then '{"profile":"energy, logistics and engineering-oriented workforce"}'::jsonb
 when 'makassar' then '{"profile":"regional trade, logistics and service workforce"}'::jsonb
 when 'jayapura' then '{"profile":"government, service and regional trade workforce"}'::jsonb else human_resources end,
natural_resources=case city_key
 when 'pekanbaru' then '{"regional_link":["oil_and_gas","forestry","plantation"]}'::jsonb
 when 'balikpapan' then '{"regional_link":["oil_and_gas","energy"]}'::jsonb
 when 'palembang' then '{"regional_link":["oil_and_gas","coal","plantation"]}'::jsonb
 when 'medan' then '{"regional_link":["plantation","agriculture","forestry"]}'::jsonb
 when 'makassar' then '{"regional_link":["fisheries","agriculture","maritime"]}'::jsonb
 when 'jayapura' then '{"regional_link":["forestry","fisheries","mining_hinterland"]}'::jsonb
 when 'denpasar' then '{"regional_link":["agriculture","fisheries","water_resources"]}'::jsonb
 else '{"regional_link":"surrounding hinterland supplies"}'::jsonb end,
political_profile=jsonb_build_object('government_level','city','local_government','mayor_and_city_council','simulation','local_policy_budget_and_approval')
where active=true;