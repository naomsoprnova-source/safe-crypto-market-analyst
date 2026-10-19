# مراجع ومراجعة المصدر

- المصدر الذي روجع: https://github.com/kukapay/crypto-skills عند الالتزام `868a437f8dcb8ce72669a5a67dd6a016951ef29a`.
- تتضمن `trading-strategist/scripts/calculate_ta.py` الأصلية `signal_line = macd_line`، وهو بديل مؤقت لا يحسب EMA9. كما تسمي حجم آخر شمعة حجمًا لـ24 ساعة، وتحسب RSI بمتوسط نافذة بسيطة لا Wilder. لم نشغل تلك الشفرة ولم نستورد الحزمة الكاملة.
- تضم الحزمة الأصلية أيضًا مهارات إرسال معاملات ونشر عقود؛ لا حاجة إليها لطلب التحليل، ولم نثبتها.
- تمت مقارنة المجموعة الأوسع https://github.com/agiprolabs/claude-trading-skills كمرجع بحثي فقط؛ لم نراجع أو نثبت جميع مهاراتها ولم نعتبر ادعاءاتها ضمان جودة أو أرباح.
- مرجع MACD: https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/macd يحدد خط الإشارة EMA9 لسلسلة MACD.
- توثيق Binance للنقاط العامة بلا مصادقة: https://developers.binance.com/en/docs/products/spot/faqs/market_data_only
- جذر السوق الفوري: https://data-api.binance.vision ؛ `/api/v3/time` و`/api/v3/ticker/24hr` و`/api/v3/klines`.
- سياق العقود العامة الاختياري: https://fapi.binance.com ؛ `/fapi/v1/premiumIndex` و`/fapi/v1/openInterest`. لا تعرض هذه النقاط رصيد المستخدم أو صفقاته.

السكربت الجديد مكتوب مستقلًا ولا يحتوي صلاحيات حساب أو إنشاء أوامر. كل اتصالاته GET بقائمة سماح محددة. تثبيت المجلد على الحاسوب لا يثبت تسجيل المهارة على حساب Cue؛ يجب التمييز صراحة بينهما.
