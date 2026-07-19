# Corpus XML block schema

`txt2xml.py` separates each corpus block into three kinds of data:

1. The `<roundtrip-data format="coj-txt">` element contains only details
   needed to reconstruct the source TXT. Its `source-id` preserves the exact
   `ID,...` value, and each `<comment>` records the number of corpus lines that
   preceded it in `position`.
2. The `<raw-text role="processing">` element contains readable, semantic
   text. Every TXT `N@kanji` marker becomes a `<sentence n="N+1">` with
   separate `<kanji>` and `<transcription>` children. Marker tag prefixes do
   not affect the syntax hierarchy.
3. All remaining direct children of `<block>` are syntax-tree roots.

Legacy text IDs such as `1_EN_01` are exposed as canonical XML IDs such as
`EN.1.1`. IDs which are already canonical, such as `MYS.3.235a`, are retained.
`xml2txt.py` uses `source-id` when reconstructing TXT.

Example:

```xml
<block id="EN.1.1" header="ugonapar eru ... noru">
  <roundtrip-data format="coj-txt" source-id="1_EN_01">
    <comment position="0" raw="IP-MAT,IP-ARG,0@侍,*" />
  </roundtrip-data>
  <raw-text role="processing">
    <sentence n="1">
      <kanji>侍</kanji>
      <transcription>ugonapar eru</transcription>
    </sentence>
  </raw-text>
  <IP-MAT>...</IP-MAT>
</block>
```
