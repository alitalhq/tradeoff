-- Point-in-time read layer. Every read made on behalf of a session goes through these
-- functions, so nothing published or closed after the session clock can be returned.

CREATE FUNCTION bars_as_of(p_session_id bigint, p_asset_id bigint, p_timeframe bar_timeframe, p_limit integer)
RETURNS SETOF price_bar
LANGUAGE sql STABLE AS $$
    SELECT b.*
    FROM price_bar b
    JOIN sim_session s ON s.id = p_session_id
    WHERE b.asset_id = p_asset_id
      AND b.timeframe = p_timeframe
      AND b.bar_end <= s.sim_time
    ORDER BY b.bar_start DESC
    LIMIT p_limit
$$;

CREATE FUNCTION news_as_of(p_session_id bigint, p_asset_id bigint, p_limit integer)
RETURNS SETOF news
LANGUAGE sql STABLE AS $$
    SELECT n.*
    FROM news n
    JOIN sim_session s ON s.id = p_session_id
    WHERE n.published_at <= s.sim_time
      AND (p_asset_id IS NULL
           OR EXISTS (SELECT 1 FROM news_asset na WHERE na.news_id = n.id AND na.asset_id = p_asset_id))
    ORDER BY n.published_at DESC, n.id DESC
    LIMIT p_limit
$$;

CREATE FUNCTION latest_price_as_of(p_session_id bigint, p_asset_id bigint)
RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT b.close
    FROM sim_session s
    CROSS JOIN LATERAL bars_as_of(s.id, p_asset_id, s.bar_timeframe, 1) b
    WHERE s.id = p_session_id
$$;
