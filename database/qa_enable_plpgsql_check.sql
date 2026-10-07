-- QA tooling: enable Supabase's plpgsql_check extension for production function linting.
create extension if not exists plpgsql_check;
