-- leobook_check_auth_identifier: fast existence check for email/phone in auth.users

CREATE OR REPLACE FUNCTION public.leobook_check_auth_identifier(p_identifier text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $func$
DECLARE
  v text := trim(p_identifier);
  v_lower text;
BEGIN
  IF v IS NULL OR length(v) = 0 THEN
    RETURN false;
  END IF;
  v_lower := lower(v);
  IF position('@' in v) > 0 THEN
    RETURN EXISTS (
      SELECT 1 FROM auth.users u
      WHERE u.email IS NOT NULL AND lower(trim(u.email)) = v_lower
    );
  END IF;
  RETURN EXISTS (
    SELECT 1 FROM auth.users u
    WHERE u.phone IS NOT NULL AND (
      trim(u.phone) = v
      OR trim(u.phone) = replace(replace(v, ' ', ''), '-', '')
    )
  );
END;
$func$;

REVOKE ALL ON FUNCTION public.leobook_check_auth_identifier(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.leobook_check_auth_identifier(text) TO service_role;

CREATE TABLE IF NOT EXISTS public.user_football_vault (
  user_id uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
  ciphertext text NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  terms_accepted_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.user_football_vault ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.user_football_vault FROM anon, authenticated;
GRANT ALL ON public.user_football_vault TO service_role;

CREATE TABLE IF NOT EXISTS public.user_device_fingerprint (
  user_id uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
  proxy_server text,
  user_agent text,
  viewport_w integer,
  viewport_h integer,
  auto_platform text,
  auto_device_model text,
  auto_os_version text,
  auto_locale text,
  auto_screen_w integer,
  auto_screen_h integer,
  auto_app_version text,
  auto_install_id text,
  auto_updated_at timestamptz
);

ALTER TABLE public.user_device_fingerprint ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users upsert own device fingerprint" ON public.user_device_fingerprint;
CREATE POLICY "Users upsert own device fingerprint"
  ON public.user_device_fingerprint
  FOR ALL
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);
GRANT SELECT, INSERT, UPDATE ON public.user_device_fingerprint TO authenticated;
