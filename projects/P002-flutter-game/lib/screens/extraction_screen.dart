import 'package:flutter/material.dart';
import '../systems/extraction_system.dart';

/// タルコフ的抽出選択画面
/// ウェーブクリア後 or ボス撃破後に表示する
class ExtractionScreen extends StatefulWidget {
  final ExtractionSystem extractionSystem;
  final int totalWaves;       // ステージ全ウェーブ数
  final int currentWave;      // クリアしたウェーブ番号
  final VoidCallback onExtract;    // 「脱出する」→ result_screen へ
  final VoidCallback onContinue;   // 「続行する」→ 次ウェーブへ

  const ExtractionScreen({
    super.key,
    required this.extractionSystem,
    required this.totalWaves,
    required this.currentWave,
    required this.onExtract,
    required this.onContinue,
  });

  @override
  State<ExtractionScreen> createState() => _ExtractionScreenState();
}

class _ExtractionScreenState extends State<ExtractionScreen>
    with TickerProviderStateMixin {
  late final AnimationController _entranceCtrl;
  late final Animation<double> _entranceOpacity;

  // 抽出アニメーション制御
  late final AnimationController _extractCtrl;
  late final Animation<double> _progressAnim;

  bool _isExtracting = false;

  @override
  void initState() {
    super.initState();

    _entranceCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 500),
    )..forward();
    _entranceOpacity = CurvedAnimation(
      parent: _entranceCtrl,
      curve: Curves.easeIn,
    );

    _extractCtrl = AnimationController(
      vsync: this,
      duration: const Duration(
          milliseconds: (ExtractionSystem.extractionDurationSeconds * 1000).toInt()),
    );
    _progressAnim = _extractCtrl;

    _extractCtrl.addStatusListener((status) {
      if (status == AnimationStatus.completed) {
        widget.extractionSystem.beginExtraction();
        widget.onExtract();
      }
    });
  }

  @override
  void dispose() {
    _entranceCtrl.dispose();
    _extractCtrl.dispose();
    super.dispose();
  }

  // ---- ビルド ----

  @override
  Widget build(BuildContext context) {
    final ex = widget.extractionSystem;
    final atRisk = ex.atRiskItems;
    final secured = ex.securedItems;
    final isLastWave = widget.currentWave >= widget.totalWaves;

    return FadeTransition(
      opacity: _entranceOpacity,
      child: Scaffold(
        backgroundColor: const Color(0xE8050510),
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
            child: Column(
              children: [
                // ヘッダー
                _buildHeader(),
                const SizedBox(height: 16),
                // ウェーブ進行インジケータ
                _buildWaveProgress(),
                const SizedBox(height: 20),
                // アイテム一覧
                Expanded(
                  child: _buildItemList(atRisk: atRisk, secured: secured),
                ),
                // 抽出プログレスバー（抽出中のみ表示）
                if (_isExtracting) ...[
                  const SizedBox(height: 12),
                  _buildExtractionProgress(),
                ],
                const SizedBox(height: 16),
                // ボタン行
                if (\!_isExtracting)
                  _buildActionButtons(
                    atRisk: atRisk,
                    isLastWave: isLastWave,
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Column(
      children: [
        const Text(
          '⚠️ 脱出判断',
          style: TextStyle(
            color: Color(0xFFFFCA28),
            fontSize: 22,
            fontWeight: FontWeight.bold,
            letterSpacing: 1.5,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          'atRisk アイテムは脱出しないとロストします',
          style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 12),
        ),
      ],
    );
  }

  Widget _buildWaveProgress() {
    return Row(
      children: List.generate(widget.totalWaves, (i) {
        final done = i < widget.currentWave;
        final current = i == widget.currentWave - 1;
        return Expanded(
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 2),
            height: 6,
            decoration: BoxDecoration(
              color: done
                  ? const Color(0xFF69F0AE)
                  : current
                      ? const Color(0xFFFFCA28)
                      : Colors.white12,
              borderRadius: BorderRadius.circular(3),
            ),
          ),
        );
      }),
    );
  }

  Widget _buildItemList({
    required List<ExtractionItem> atRisk,
    required List<ExtractionItem> secured,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (atRisk.isNotEmpty) ...[
          _sectionLabel('🔴 atRisk（脱出しないとロスト）',
              const Color(0xFFEF5350)),
          const SizedBox(height: 6),
          ...atRisk.map((item) => _ItemRow(item: item, isAtRisk: true)),
          const SizedBox(height: 12),
          // リスク総額
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: const Color(0x22EF5350),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0x44EF5350)),
            ),
            child: Row(
              children: [
                const Text('💀 ロストリスク総額: ',
                    style: TextStyle(color: Colors.white70, fontSize: 12)),
                Text('${widget.extractionSystem.totalAtRiskGoldValue} G',
                    style: const TextStyle(
                        color: Color(0xFFEF5350),
                        fontWeight: FontWeight.bold,
                        fontSize: 14)),
              ],
            ),
          ),
        ] else
          _emptyState('atRiskアイテムなし — 安全に続行できます'),
        if (secured.isNotEmpty) ...[
          const SizedBox(height: 16),
          _sectionLabel('🟢 Secured（確定所持）', const Color(0xFF69F0AE)),
          const SizedBox(height: 6),
          ...secured.map((item) => _ItemRow(item: item, isAtRisk: false)),
        ],
      ],
    );
  }

  Widget _sectionLabel(String text, Color color) => Text(
        text,
        style: TextStyle(
            color: color, fontWeight: FontWeight.bold, fontSize: 13),
      );

  Widget _emptyState(String text) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.05),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Center(
          child: Text(text,
              style: const TextStyle(color: Colors.white38, fontSize: 12)),
        ),
      );

  Widget _buildExtractionProgress() {
    return AnimatedBuilder(
      animation: _progressAnim,
      builder: (_, __) => Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('抽出中...',
                  style: TextStyle(color: Color(0xFF69F0AE), fontSize: 13)),
              Text('${(_progressAnim.value * 100).toStringAsFixed(0)}%',
                  style: const TextStyle(
                      color: Color(0xFF69F0AE), fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: _progressAnim.value,
              minHeight: 8,
              backgroundColor: Colors.white12,
              valueColor: const AlwaysStoppedAnimation(Color(0xFF69F0AE)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionButtons({
    required List<ExtractionItem> atRisk,
    required bool isLastWave,
  }) {
    return Column(
      children: [
        // 「脱出する」
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: _startExtraction,
            icon: const Text('🚀', style: TextStyle(fontSize: 18)),
            label: const Text('脱出する（アイテムを確保）',
                style: TextStyle(fontWeight: FontWeight.bold)),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF1B5E20),
              foregroundColor: const Color(0xFF69F0AE),
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10)),
            ),
          ),
        ),
        if (\!isLastWave) ...[
          const SizedBox(height: 10),
          // 「続行する」
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: () {
                widget.extractionSystem.continueWithRisk();
                widget.onContinue();
              },
              icon: Text(
                atRisk.isNotEmpty ? '⚠️' : '➡️',
                style: const TextStyle(fontSize: 16),
              ),
              label: Text(
                atRisk.isNotEmpty
                    ? '続行する（${atRisk.length}個のリスクを承知）'
                    : '続行する（次のウェーブへ）',
                style: const TextStyle(fontSize: 13),
              ),
              style: OutlinedButton.styleFrom(
                foregroundColor: atRisk.isNotEmpty
                    ? const Color(0xFFFFCA28)
                    : Colors.white70,
                side: BorderSide(
                  color: atRisk.isNotEmpty
                      ? const Color(0xFFFFCA28)
                      : Colors.white24,
                ),
                padding: const EdgeInsets.symmetric(vertical: 12),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10)),
              ),
            ),
          ),
        ],
      ],
    );
  }

  void _startExtraction() {
    setState(() => _isExtracting = true);
    _extractCtrl.forward();
  }
}

// ---- ItemRow ----

class _ItemRow extends StatelessWidget {
  final ExtractionItem item;
  final bool isAtRisk;

  const _ItemRow({required this.item, required this.isAtRisk});

  @override
  Widget build(BuildContext context) {
    final color = isAtRisk ? const Color(0xFFEF5350) : const Color(0xFF69F0AE);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(item.displayName,
                style: const TextStyle(color: Colors.white, fontSize: 13)),
          ),
          if (item.isCosmeticOnly)
            const Text('🎨',
                style: TextStyle(fontSize: 12, color: Colors.white38)),
          const SizedBox(width: 6),
          Text('${item.goldValue} G',
              style: TextStyle(
                  color: isAtRisk ? const Color(0xFFEF9A9A) : const Color(0xFF69F0AE),
                  fontSize: 12,
                  fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }
}
