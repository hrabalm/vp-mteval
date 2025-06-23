"""
SQL queries for finding top-10 confirmed and unconfirmed n-grams in translation runs.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Any


async def get_confirmed_unconfirmed_ngrams(
    session: AsyncSession, run_id: int, tokenizer: str
) -> dict[int, dict[str, list[dict[str, Any]]]]:
    """
    Aggregated across the whole run and filtered by tokenizer.
    Returns a mapping from n to a dict with two lists:
      - 'confirmed': top-10 confirmed n-grams with their ref/target counts & confirmed_size
      - 'unconfirmed': top-10 unconfirmed n-grams with their ref/target counts & unconfirmed_size
    Each list item is a dict { 'ngram': str, 'count_ref': int, 'count_tgt': int,
                               'confirmed_size': int, 'unconfirmed_size': int }.
    """
    sql = text("""
    WITH
      ref AS (
        SELECT st.n,
               elem_ref AS ngram,
               COUNT(*) AS ref_count
        FROM segment_translation_ngrams st,
             jsonb_array_elements_text(st.ngrams_ref) AS elem_ref
        WHERE st.run_id = :run_id
          AND st.tokenizer = :tokenizer
        GROUP BY st.n, elem_ref
      ),
      trans AS (
        SELECT st.n,
               elem_trans AS ngram,
               COUNT(*) AS trans_count
        FROM segment_translation_ngrams st,
             jsonb_array_elements_text(st.ngrams) AS elem_trans
        WHERE st.run_id = :run_id
          AND st.tokenizer = :tokenizer
        GROUP BY st.n, elem_trans
      ),
      all_counts AS (
        SELECT COALESCE(r.n, t.n) AS n,
               COALESCE(r.ngram, t.ngram) AS ngram,
               COALESCE(r.ref_count, 0) AS ref_count,
               COALESCE(t.trans_count, 0) AS trans_count,
               LEAST(COALESCE(r.ref_count, 0), COALESCE(t.trans_count, 0))        AS confirmed_size,
               GREATEST(COALESCE(t.trans_count, 0) - COALESCE(r.ref_count, 0), 0) AS unconfirmed_size
        FROM ref r
        FULL JOIN trans t USING (n, ngram)
      )
    SELECT
      ac.n,
      (
        SELECT jsonb_agg(
          jsonb_build_object(
            'ngram', g.ngram,
            'count_ref', g.ref_count,
            'count_tgt', g.trans_count,
            'confirmed_size', g.confirmed_size,
            'unconfirmed_size', g.unconfirmed_size
          )
        )
        FROM (
          SELECT ngram, ref_count, trans_count, confirmed_size, unconfirmed_size
          FROM all_counts
          WHERE n = ac.n
          ORDER BY confirmed_size DESC
          LIMIT 10
        ) AS g
      ) AS confirmed,
      (
        SELECT jsonb_agg(
          jsonb_build_object(
            'ngram', u.ngram,
            'count_ref', u.ref_count,
            'count_tgt', u.trans_count,
            'confirmed_size', u.confirmed_size,
            'unconfirmed_size', u.unconfirmed_size
          )
        )
        FROM (
          SELECT ngram, ref_count, trans_count, confirmed_size, unconfirmed_size
          FROM all_counts
          WHERE n = ac.n
          ORDER BY unconfirmed_size DESC
          LIMIT 10
        ) AS u
      ) AS unconfirmed
    FROM (SELECT DISTINCT n FROM all_counts) AS ac
    ORDER BY ac.n;
    """)

    cursor = await session.execute(sql, {"run_id": run_id, "tokenizer": tokenizer})
    rows = cursor.fetchall()

    output: dict[int, dict[str, list[dict[str, int]]]] = {}
    for n, confirmed_list, unconfirmed_list in rows:
        output[n] = {
            "confirmed": confirmed_list or [],
            "unconfirmed": unconfirmed_list or [],
        }
    return output
