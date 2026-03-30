-- trial_reminder_cron.sql: Scheduled LeoBook premium alerts.
-- Instructions: Run this in the Supabase SQL Editor.

-- Enable pg_cron if not already enabled
-- (Found in Dashboard -> Database -> Extensions)
-- create extension if not exists pg_cron;

-- 1. Create a function that identifies users with 15 days left
--    and hits the Edge Function for each.

create or replace function check_trial_reminders()
returns void
language plpgsql
security definer
as $$
declare
  user_row record;
begin
  for user_row in 
    select 
      id, 
      email, 
      trial_end_date 
    from profiles 
    where trial_end_date::date = (now() + interval '15 days')::date
    and subscription_status = 'free' -- Only remind if not already upgraded
  loop
    -- Call the Edge Function
    perform http_post(
      'https://[YOUR_PROJECT_REF].functions.supabase.co/trigger-email',
      json_build_object(
        'template', 'trial_reminder',
        'email', user_row.email,
        'data', json_build_object('trial_end', user_row.trial_end_date)
      )::text,
      'application/json'
    );
  end loop;
end;
$$;

-- 2. Schedule the function to run every day at 09:00 UTC
-- select cron.schedule('trial-reminder-daily', '0 9 * * *', 'select check_trial_reminders()');
