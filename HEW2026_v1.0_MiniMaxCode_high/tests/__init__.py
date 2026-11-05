"""テストパッケージ宣言。

このファイルが無いと pytest が `import tests.conftest` を試した際、
プロジェクト内の tests/ ではなく Python の site-packages/tests/
（ultralytics が配置する別パッケージ）を拾ってしまう。そのままでは
torch → pyarrow が読み込まれ、ネイティブアクセス違反で Python ごと
クラッシュする（HEW2026 の作業記録に残っている既知の不具合）。

プロジェクト側の tests/ を明示的に「パッケージ」として宣言し、
site-packages 側の同名パッケージより優先させる。
"""
