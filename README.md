# molcrafts-ci — data

The published engineering index. This branch is **not** code and shares no
history with `master`.

```
index/<project>/<record>.jsonl        append-only history
snapshots/<project>/<record>/<generation>/<snapshot_id>.json
```

Written only by `actions/submit`, which producers call from their own CI. The
specification's §18 diagram names this branch: keeping the data here is what
stops ingest commits from landing in the code history and stops a clone of the
source from carrying every snapshot ever published.

Do not commit here by hand.
