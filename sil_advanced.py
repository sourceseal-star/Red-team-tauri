#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sil_advanced.py — Datos de aprendizaje avanzado de chino para Sol.

Niveles:
  - HSK 3: intermedio-bajo (600 palabras, gramática básica)
  - HSK 4: intermedio (1200 palabras, patrones complejos)
  - HSK 5: intermedio-alto (2500 palabras, lectura y expresión)
  - Chengyu: modismos de 4 caracteres
  - Gramática: patrones sintácticos clave
  - Conversación: frases útiles en contextos profesionales
  - Tech: vocabulario de tecnología y ciberseguridad

Diseñado para alguien que YA sabe basics (saludos, números, comida)
y quiere avanzar a un nivel profesional.
"""

# ═══════════════════════════════════════════════════════════════════
# HSK 3 — Intermedio-bajo
# ═══════════════════════════════════════════════════════════════════
HSK3_VOCAB = [
    {"word": "安排", "pinyin": "ānpái", "meaning": "arreglar, organizar", "pos": "verb", "example": "我安排明天的会议。", "example_tr": "He organizado la reunión de mañana."},
    {"word": "按照", "pinyin": "ànzhào", "meaning": "según, de acuerdo con", "pos": "prep", "example": "按照计划执行。", "example_tr": "Ejecutar según el plan."},
    {"word": "把握", "pinyin": "bǎwò", "meaning": "agarrar, estar seguro", "pos": "verb", "example": "我有把握完成。", "example_tr": "Estoy seguro de poder completarlo."},
    {"word": "保护", "pinyin": "bǎohù", "meaning": "proteger", "pos": "verb", "example": "保护数据安全。", "example_tr": "Proteger la seguridad de los datos."},
    {"word": "保证", "pinyin": "bǎozhèng", "meaning": "garantizar, asegurar", "pos": "verb", "example": "我保证按时完成。", "example_tr": "Garantizo terminar a tiempo."},
    {"word": "不仅...而且", "pinyin": "bùjǐn...érqiě", "meaning": "no solo...sino también", "pos": "conj", "example": "他不仅聪明而且努力。", "example_tr": "No solo es inteligente sino también trabajador."},
    {"word": "参加", "pinyin": "cānjiā", "meaning": "participar, unirse", "pos": "verb", "example": "参加安全培训。", "example_tr": "Participar en capacitación de seguridad."},
    {"word": "曾经", "pinyin": "céngjīng", "meaning": "alguna vez (pasado)", "pos": "adv", "example": "我曾经去过中国。", "example_tr": "Alguna vez fui a China."},
    {"word": "出发", "pinyin": "chūfā", "meaning": "salir, partir", "pos": "verb", "example": "我们早上出发。", "example_tr": "Salimos por la mañana."},
    {"word": "除了...以外", "pinyin": "chúle...yǐwài", "meaning": "excepto, además de", "pos": "conj", "example": "除了英语以外，还会中文。", "example_tr": "Además de inglés, también sabe chino."},
    {"word": "达到", "pinyin": "dádào", "meaning": "alcanzar, lograr", "pos": "verb", "example": "达到目标。", "example_tr": "Alcanzar la meta."},
    {"word": "担心", "pinyin": "dānxīn", "meaning": "preocuparse", "pos": "verb", "example": "不用担心。", "example_tr": "No te preocupes."},
    {"word": "当时", "pinyin": "dāngshí", "meaning": "en ese momento", "pos": "noun", "example": "当时我在家。", "example_tr": "En ese momento estaba en casa."},
    {"word": "当然", "pinyin": "dāngrán", "meaning": "por supuesto", "pos": "adv", "example": "当然可以。", "example_tr": "Por supuesto que sí."},
    {"word": "发现", "pinyin": "fāxiàn", "meaning": "descubrir, encontrar", "pos": "verb", "example": "发现了漏洞。", "example_tr": "Descubrió una vulnerabilidad."},
    {"word": "反正", "pinyin": "fǎnzhèng", "meaning": "de todos modos", "pos": "adv", "example": "反正都要做。", "example_tr": "De todos modos hay que hacerlo."},
    {"word": "丰富", "pinyin": "fēngfù", "meaning": "abundante, rico", "pos": "adj", "example": "经验丰富。", "example_tr": "Tener mucha experiencia."},
    {"word": "感谢", "pinyin": "gǎnxiè", "meaning": "agradecer", "pos": "verb", "example": "感谢你的帮助。", "example_tr": "Gracias por tu ayuda."},
    {"word": "根据", "pinyin": "gēnjù", "meaning": "según, basarse en", "pos": "prep", "example": "根据报告分析。", "example_tr": "Analizar según el informe."},
    {"word": "关心", "pinyin": "guānxīn", "meaning": "preocuparse por", "pos": "verb", "example": "关心安全问题。", "example_tr": "Preocuparse por la seguridad."},
    {"word": "过程", "pinyin": "guòchéng", "meaning": "proceso", "pos": "noun", "example": "学习过程。", "example_tr": "Proceso de aprendizaje."},
    {"word": "及时", "pinyin": "jíshí", "meaning": "a tiempo, puntual", "pos": "adv", "example": "及时更新系统。", "example_tr": "Actualizar el sistema a tiempo."},
    {"word": "继续", "pinyin": "jìxù", "meaning": "continuar", "pos": "verb", "example": "继续工作。", "example_tr": "Continuar trabajando."},
    {"word": "建议", "pinyin": "jiànyì", "meaning": "sugerir, proponer", "pos": "verb", "example": "我建议升级。", "example_tr": "Sugiero actualizar."},
    {"word": "解决", "pinyin": "jiějué", "meaning": "resolver, solucionar", "pos": "verb", "example": "解决问题。", "example_tr": "Resolver el problema."},
    {"word": "尽管", "pinyin": "jǐnquǎn", "meaning": "a pesar de", "pos": "conj", "example": "尽管很难，也要做。", "example_tr": "A pesar de ser difícil, hay que hacerlo."},
    {"word": "经验", "pinyin": "jīngyàn", "meaning": "experiencia", "pos": "noun", "example": "工作经验。", "example_tr": "Experiencia laboral."},
    {"word": "耐心", "pinyin": "nàixīn", "meaning": "paciencia", "pos": "noun/adj", "example": "要有耐心。", "example_tr": "Hay que tener paciencia."},
    {"word": "普遍", "pinyin": "pǔbiàn", "meaning": "generalizado, común", "pos": "adj", "example": "普遍存在的问题。", "example_tr": "Un problema común."},
    {"word": "缺乏", "pinyin": "quēfá", "meaning": "carecer, faltar", "pos": "verb", "example": "缺乏资源。", "example_tr": "Falta de recursos."},
    {"word": "认为", "pinyin": "rènwéi", "meaning": "considerar, pensar", "pos": "verb", "example": "我认为可以。", "example_tr": "Creo que es posible."},
    {"word": "适合", "pinyin": "shìhé", "meaning": "adecuado, apropiado", "pos": "verb", "example": "适合这个职位。", "example_tr": "Adecuado para este puesto."},
    {"word": "提供", "pinyin": "tígōng", "meaning": "proveer, ofrecer", "pos": "verb", "example": "提供技术支持。", "example_tr": "Proveer soporte técnico."},
    {"word": "通过", "pinyin": "tōngguò", "meaning": "mediante, aprobar", "pos": "prep/verb", "example": "通过考试。", "example_tr": "Aprobar el examen."},
    {"word": "同时", "pinyin": "tóngshí", "meaning": "al mismo tiempo", "pos": "adv", "example": "同时处理多个任务。", "example_tr": "Manejar múltiples tareas a la vez."},
    {"word": "突出", "pinyin": "tūchū", "meaning": "destacar, sobresalir", "pos": "verb/adj", "example": "突出的问题。", "example_tr": "Un problema destacado."},
    {"word": "往往", "pinyin": "wǎngwǎng", "meaning": "a menudo, frecuentemente", "pos": "adv", "example": "往往会出错。", "example_tr": "A menudo comete errores."},
    {"word": "明显", "pinyin": "míngxiǎn", "meaning": "obvio, evidente", "pos": "adj", "example": "明显的错误。", "example_tr": "Un error obvio."},
    {"word": "需要", "pinyin": "xūyào", "meaning": "necesitar", "pos": "verb", "example": "需要更多时间。", "example_tr": "Necesitar más tiempo."},
    {"word": "严重", "pinyin": "yánzhòng", "meaning": "grave, serio", "pos": "adj", "example": "严重的安全问题。", "example_tr": "Un problema de seguridad grave."},
    {"word": "一般", "pinyin": "yìbān", "meaning": "general, normal", "pos": "adj", "example": "一般情况下。", "example_tr": "En circunstancias normales."},
    {"word": "因此", "pinyin": "yīncǐ", "meaning": "por lo tanto", "pos": "conj", "example": "因此要小心。", "example_tr": "Por lo tanto, hay que tener cuidado."},
    {"word": "影响", "pinyin": "yǐngxiǎng", "meaning": "influenciar, afectar", "pos": "verb", "example": "影响系统性能。", "example_tr": "Afectar el rendimiento del sistema."},
    {"word": "终于", "pinyin": "zhōngyú", "meaning": "finalmente, por fin", "pos": "adv", "example": "终于完成了。", "example_tr": "Finalmente terminado."},
    {"word": "重视", "pinyin": "zhòngshì", "meaning": "valorar, dar importancia", "pos": "verb", "example": "重视安全。", "example_tr": "Dar importancia a la seguridad."},
    {"word": "总结", "pinyin": "zǒngjié", "meaning": "resumir, concluir", "pos": "verb", "example": "总结经验。", "example_tr": "Resumir la experiencia."},
    {"word": "作用", "pinyin": "zuòyòng", "meaning": "función, papel", "pos": "noun", "example": "起重要作用。", "example_tr": "Desempeñar un papel importante."},
]

# ═══════════════════════════════════════════════════════════════════
# HSK 4 — Intermedio
# ═══════════════════════════════════════════════════════════════════
HSK4_VOCAB = [
    {"word": "把握", "pinyin": "bǎwò", "meaning": "certeza, control", "pos": "noun", "example": "我有把握。", "example_tr": "Tengo certeza."},
    {"word": "伴随", "pinyin": "bànsuí", "meaning": "acompañar, ir con", "pos": "verb", "example": "伴随着发展。", "example_tr": "Acompañado del desarrollo."},
    {"word": "变动", "pinyin": "biàndòng", "meaning": "cambio, alteración", "pos": "noun", "example": "人事变动。", "example_tr": "Cambios de personal."},
    {"word": "不便", "pinyin": "bùbiàn", "meaning": "inconveniente", "pos": "adj", "example": "给您带来不便。", "example_tr": "Le causa inconveniencia."},
    {"word": "层出不穷", "pinyin": "céng chū bù qióng", "meaning": "surgir sin cesar", "pos": "chengyu", "example": "问题层出不穷。", "example_tr": "Los problemas surgen sin cesar."},
    {"word": "成本", "pinyin": "chéngběn", "meaning": "costo", "pos": "noun", "example": "降低成本。", "example_tr": "Reducir costos."},
    {"word": "承担", "pinyin": "chéngdān", "meaning": "asumir, hacerse cargo", "pos": "verb", "example": "承担责任。", "example_tr": "Asumir la responsabilidad."},
    {"word": "诚实", "pinyin": "chéngshí", "meaning": "honesto", "pos": "adj", "example": "诚实回答。", "example_tr": "Responder con honestidad."},
    {"word": "重复", "pinyin": "chóngfù", "meaning": "repetir", "pos": "verb", "example": "避免重复。", "example_tr": "Evitar repetición."},
    {"word": "打断", "pinyin": "dǎduàn", "meaning": "interrumpir", "pos": "verb", "example": "别打断我。", "example_tr": "No me interrumpas."},
    {"word": "担当", "pinyin": "dāndāng", "meaning": "asumir responsabilidad", "pos": "verb", "example": "担当重任。", "example_tr": "Asumir grandes responsabilidades."},
    {"word": "调查", "pinyin": "diàochá", "meaning": "investigar", "pos": "verb", "example": "调查原因。", "example_tr": "Investigar la causa."},
    {"word": "独立", "pinyin": "dúlì", "meaning": "independiente", "pos": "adj", "example": "独立完成。", "example_tr": "Completar independientemente."},
    {"word": "额外", "pinyin": "éwài", "meaning": "extra, adicional", "pos": "adj", "example": "额外费用。", "example_tr": "Costo adicional."},
    {"word": "放弃", "pinyin": "fàngqì", "meaning": "renunciar, abandonar", "pos": "verb", "example": "不放弃。", "example_tr": "No rendirse."},
    {"word": "分工", "pinyin": "fēngōng", "meaning": "división de trabajo", "pos": "noun", "example": "明确分工。", "example_tr": "División clara del trabajo."},
    {"word": "抱怨", "pinyin": "bàoyuàn", "meaning": "quejarse", "pos": "verb", "example": "不要抱怨。", "example_tr": "No te quejes."},
    {"word": "高效", "pinyin": "gāoxiào", "meaning": "eficiente", "pos": "adj", "example": "高效工作。", "example_tr": "Trabajo eficiente."},
    {"word": "沟通", "pinyin": "gōutōng", "meaning": "comunicarse", "pos": "verb", "example": "有效沟通。", "example_tr": "Comunicación efectiva."},
    {"word": "过度", "pinyin": "guòdù", "meaning": "excesivo", "pos": "adj", "example": "过度使用。", "example_tr": "Uso excesivo."},
    {"word": "汇报", "pinyin": "huìbào", "meaning": "reportar, informar", "pos": "verb", "example": "汇报进度。", "example_tr": "Reportar el progreso."},
    {"word": "简直", "pinyin": "jiǎnzhí", "meaning": "simplemente, casi", "pos": "adv", "example": "简直不可能。", "example_tr": "Simplemente imposible."},
    {"word": "竞争", "pinyin": "jìngzhēng", "meaning": "competir", "pos": "verb", "example": "市场竞争。", "example_tr": "Competencia de mercado."},
    {"word": "居然", "pinyin": "jūrán", "meaning": "inesperadamente", "pos": "adv", "example": "他居然同意了。", "example_tr": "Inesperadamente aceptó."},
    {"word": "客观", "pinyin": "kèguān", "meaning": "objetivo", "pos": "adj", "example": "客观分析。", "example_tr": "Análisis objetivo."},
    {"word": "冷静", "pinyin": "lěngjìng", "meaning": "calmado", "pos": "adj", "example": "保持冷静。", "example_tr": "Mantener la calma."},
    {"word": "耐心", "pinyin": "nàixīn", "meaning": "paciencia", "pos": "noun", "example": "耐心解释。", "example_tr": "Explicar con paciencia."},
    {"word": "恰巧", "pinyin": "qiàqiǎo", "meaning": "coincidencialmente", "pos": "adv", "example": "恰巧碰到。", "example_tr": "Coincidir casualmente."},
    {"word": "深入", "pinyin": "shēnrù", "meaning": "profundo, detallado", "pos": "adj/verb", "example": "深入分析。", "example_tr": "Análisis profundo."},
    {"word": "实施", "pinyin": "shíshī", "meaning": "implementar", "pos": "verb", "example": "实施方案。", "example_tr": "Implementar el plan."},
    {"word": "探讨", "pinyin": "tàntǎo", "meaning": "explorar, discutir", "pos": "verb", "example": "探讨解决方案。", "example_tr": "Explorar soluciones."},
    {"word": "体现", "pinyin": "tǐxiàn", "meaning": "reflejar, encarnar", "pos": "verb", "example": "体现了专业精神。", "example_tr": "Refleja profesionalismo."},
    {"word": "体现", "pinyin": "tǐxiàn", "meaning": "reflejar, manifestar", "pos": "verb", "example": "体现了价值。", "example_tr": "Refleja valor."},
    {"word": "调整", "pinyin": "tiáozhěng", "meaning": "ajustar", "pos": "verb", "example": "调整策略。", "example_tr": "Ajustar la estrategia."},
    {"word": "协商", "pinyin": "xiéshāng", "meaning": "negociar, consultar", "pos": "verb", "example": "协商解决。", "example_tr": "Resolver mediante negociación."},
    {"word": "延迟", "pinyin": "yánchí", "meaning": "retrasar", "pos": "verb", "example": "项目延迟。", "example_tr": "Retraso del proyecto."},
    {"word": "一律", "pinyin": "yīlǜ", "meaning": "sin excepción", "pos": "adv", "example": "一律平等。", "example_tr": "Todos por igual."},
    {"word": "责任", "pinyin": "zérèn", "meaning": "responsabilidad", "pos": "noun", "example": "负责任。", "example_tr": "Ser responsable."},
    {"word": "整顿", "pinyin": "zhěngdùn", "meaning": "reorganizar", "pos": "verb", "example": "整顿秩序。", "example_tr": "Reorganizar el orden."},
    {"word": "证据", "pinyin": "zhèngjù", "meaning": "evidencia", "pos": "noun", "example": "收集证据。", "example_tr": "Recopilar evidencia."},
    {"word": "指导", "pinyin": "zhǐdǎo", "meaning": "guiar, instruir", "pos": "verb", "example": "指导工作。", "example_tr": "Guiar el trabajo."},
    {"word": "逐步", "pinyin": "zhúbù", "meaning": "paso a paso", "pos": "adv", "example": "逐步推进。", "example_tr": "Avanzar paso a paso."},
    {"word": "专门", "pinyin": "zhuānmén", "meaning": "específico, dedicado", "pos": "adj", "example": "专门技术。", "example_tr": "Tecnología especializada."},
    {"word": "总结", "pinyin": "zǒngjié", "meaning": "conclusión, resumen", "pos": "noun/verb", "example": "会议总结。", "example_tr": "Resumen de la reunión."},
]

# ═══════════════════════════════════════════════════════════════════
# HSK 5 — Intermedio-alto
# ═══════════════════════════════════════════════════════════════════
HSK5_VOCAB = [
    {"word": "把握", "pinyin": "bǎwò", "meaning": "grado de certeza", "pos": "noun", "example": "有把握成功。", "example_tr": "Tener certeza del éxito."},
    {"word": "保留", "pinyin": "bǎoliú", "meaning": "conservar, reservar", "pos": "verb", "example": "保留意见。", "example_tr": "Reservarse la opinión."},
    {"word": "背景", "pinyin": "bèijǐng", "meaning": "contexto, antecedentes", "pos": "noun", "example": "技术背景。", "example_tr": "Contexto técnico."},
    {"word": "标准", "pinyin": "biāozhǔn", "meaning": "estándar, criterio", "pos": "noun", "example": "符合标准。", "example_tr": "Cumplir con el estándar."},
    {"word": "辩论", "pinyin": "biànlùn", "meaning": "debatir", "pos": "verb", "example": "辩论问题。", "example_tr": "Debatir el problema."},
    {"word": "部署", "pinyin": "bùshǔ", "meaning": "desplegar (militar/IT)", "pos": "verb", "example": "部署系统。", "example_tr": "Desplegar el sistema."},
    {"word": "操纵", "pinyin": "cāozòng", "meaning": "manipular, controlar", "pos": "verb", "example": "操纵数据。", "example_tr": "Manipular datos."},
    {"word": "测试", "pinyin": "cèshì", "meaning": "probar, testear", "pos": "verb", "example": "测试漏洞。", "example_tr": "Probar vulnerabilidades."},
    {"word": "冲击", "pinyin": "chōngjī", "meaning": "impacto, choque", "pos": "noun/verb", "example": "受到冲击。", "example_tr": "Recibir un impacto."},
    {"word": "传播", "pinyin": "chuánbō", "meaning": "propagar, difundir", "pos": "verb", "example": "传播信息。", "example_tr": "Propagar información."},
    {"word": "脆弱", "pinyin": "cuìruò", "meaning": "frágil, vulnerable", "pos": "adj", "example": "脆弱的系统。", "example_tr": "Sistema frágil."},
    {"word": "防范", "pinyin": "fángfàn", "meaning": "prevenir, guardarse", "pos": "verb", "example": "防范攻击。", "example_tr": "Prevenir ataques."},
    {"word": "风险", "pinyin": "fēngxiǎn", "meaning": "riesgo", "pos": "noun", "example": "评估风险。", "example_tr": "Evaluar riesgos."},
    {"word": "隔离", "pinyin": "gélí", "meaning": "aislar, segregar", "pos": "verb", "example": "隔离网络。", "example_tr": "Aislar la red."},
    {"word": "监控", "pinyin": "jiānkòng", "meaning": "monitorear", "pos": "verb", "example": "实时监控。", "example_tr": "Monitoreo en tiempo real."},
    {"word": "滥用", "pinyin": "làyòng", "meaning": "abusar, usar mal", "pos": "verb", "example": "滥用权限。", "example_tr": "Abusar de permisos."},
    {"word": "漏洞", "pinyin": "lòudòng", "meaning": "vulnerabilidad, brecha", "pos": "noun", "example": "安全漏洞。", "example_tr": "Vulnerabilidad de seguridad."},
    {"word": "密码", "pinyin": "mìmǎ", "meaning": "contraseña, cifrado", "pos": "noun", "example": "修改密码。", "example_tr": "Cambiar la contraseña."},
    {"word": "密钥", "pinyin": "mìyào", "meaning": "clave criptográfica", "pos": "noun", "example": "加密密钥。", "example_tr": "Clave de cifrado."},
    {"word": "入侵", "pinyin": "rùqīn", "meaning": "intrusión, invadir", "pos": "verb", "example": "入侵检测。", "example_tr": "Detección de intrusiones."},
    {"word": "审计", "pinyin": "shěnjì", "meaning": "auditar", "pos": "verb", "example": "安全审计。", "example_tr": "Auditoría de seguridad."},
    {"word": "授权", "pinyin": "shòuquán", "meaning": "autorizar", "pos": "verb", "example": "授权访问。", "example_tr": "Autorizar acceso."},
    {"word": "威胁", "pinyin": "wēixié", "meaning": "amenaza", "pos": "noun", "example": "安全威胁。", "example_tr": "Amenaza de seguridad."},
    {"word": "协议", "pinyin": "xiéyì", "meaning": "protocolo, acuerdo", "pos": "noun", "example": "通信协议。", "example_tr": "Protocolo de comunicación."},
    {"word": "验证", "pinyin": "yànzhèng", "meaning": "verificar, validar", "pos": "verb", "example": "身份验证。", "example_tr": "Verificación de identidad."},
    {"word": "隐私", "pinyin": "yǐnsī", "meaning": "privacidad", "pos": "noun", "example": "保护隐私。", "example_tr": "Proteger la privacidad."},
    {"word": "恶意", "pinyin": "èyì", "meaning": "malicioso", "pos": "adj", "example": "恶意软件。", "example_tr": "Software malicioso."},
    {"word": "伪造", "pinyin": "wěizào", "meaning": "falsificar", "pos": "verb", "example": "伪造证书。", "example_tr": "Falsificar certificados."},
    {"word": "拦截", "pinyin": "lánjié", "meaning": "interceptar", "pos": "verb", "example": "拦截数据包。", "example_tr": "Interceptar paquetes."},
    {"word": "渗透", "pinyin": "shèntòu", "meaning": "penetrar, infiltrar", "pos": "verb", "example": "渗透测试。", "example_tr": "Prueba de penetración."},
    {"word": "追溯", "pinyin": "zhuīsù", "meaning": "rastrear, retroceder", "pos": "verb", "example": "追溯来源。", "example_tr": "Rastrear el origen."},
    {"word": "瘫痪", "pinyin": "tānhuàn", "meaning": "paralizar", "pos": "verb", "example": "系统瘫痪。", "example_tr": "Sistema paralizado."},
    {"word": "冗余", "pinyin": "rǒngyú", "meaning": "redundancia", "pos": "noun", "example": "冗余备份。", "example_tr": "Respaldo redundante."},
    {"word": "规避", "pinyin": "guībì", "meaning": "evitar, eludir", "pos": "verb", "example": "规避风险。", "example_tr": "Evitar riesgos."},
    {"word": "追溯", "pinyin": "zhuīsù", "meaning": "rastrear", "pos": "verb", "example": "追溯源头。", "example_tr": "Rastrear la fuente."},
    {"word": "隐蔽", "pinyin": "yǐnbì", "meaning": "oculto, encubierto", "pos": "adj", "example": "隐蔽信道。", "example_tr": "Canal oculto."},
    {"word": "枚举", "pinyin": "méiju", "meaning": "enumerar", "pos": "verb", "example": "枚举攻击。", "example_tr": "Ataque de enumeración."},
    {"word": "指纹", "pinyin": "zhǐwén", "meaning": "huella digital", "pos": "noun", "example": "系统指纹。", "example_tr": "Huella del sistema."},
    {"word": "诱饵", "pinyin": "yòu'ěr", "meaning": "señuelo, cebo", "pos": "noun", "example": "蜜罐诱饵。", "example_tr": "Señuelo honeypot."},
    {"word": "迹象", "pinyin": "jìxiàng", "meaning": "indicio, señal", "pos": "noun", "example": "入侵迹象。", "example_tr": "Indicios de intrusión."},
]

# ═══════════════════════════════════════════════════════════════════
# CHENGYU — Modismos de 4 caracteres
# ═══════════════════════════════════════════════════════════════════
CHENGYU = [
    {"word": "一石二鸟", "pinyin": "yī shí èr niǎo", "meaning": "matar dos pájaros de una piedra", "literal": "una piedra dos pájaros", "example": "这个方法一石二鸟。", "example_tr": "Este método mata dos pájaros de una piedra."},
    {"word": "自相矛盾", "pinyin": "zì xiāng máo dùn", "meaning": "contradecirse a sí mismo", "literal": "lanza y escudo propios", "example": "你的说法自相矛盾。", "example_tr": "Tu argumento se contradice."},
    {"word": "画蛇添足", "pinyin": "huà shé tiān zú", "meaning": "hacer algo innecesario y arruinarlo", "literal": "dibujar serpiente añadir patas", "example": "别画蛇添足。", "example_tr": "No hagas demasiado y arruines lo bueno."},
    {"word": "亡羊补牢", "pinyin": "wáng yáng bǔ láo", "meaning": "mejor tarde que nunca", "literal": "perder oveja reparar redil", "example": "亡羊补牢，为时不晚。", "example_tr": "Mejor tarde que nunca."},
    {"word": "刻舟求剑", "pinyin": "kè zhōu qiú jiàn", "meaning": "ser obstinado ante cambios", "literal": "marcar barca buscar espada", "example": "这种方法刻舟求剑。", "example_tr": "Ese método es obsoleto ante los cambios."},
    {"word": "纸上谈兵", "pinyin": "zhǐ shàng tán bīng", "meaning": "teoría sin práctica", "literal": "en papel hablar de guerra", "example": "这只是纸上谈兵。", "example_tr": "Eso es solo teoría sin práctica."},
    {"word": "锦上添花", "pinyin": "jǐn shàng tiān huā", "meaning": "hacer algo bueno aún mejor", "literal": "en brocado añadir flores", "example": "你的建议锦上添花。", "example_tr": "Tu sugerencia lo mejora aún más."},
    {"word": "雪中送炭", "pinyin": "xuě zhōng sòng tàn", "meaning": "ayudar en momentos difíciles", "literal": "en nieve entregar carbón", "example": "你的帮助雪中送炭。", "example_tr": "Tu ayuda llegó en el momento justo."},
    {"word": "对牛弹琴", "pinyin": "duì niú tán qín", "meaning": "hablar a quien no entiende", "literal": "a buey tocar instrumento", "example": "跟他解释是对牛弹琴。", "example_tr": "Explicarle es hablar a la pared."},
    {"word": "井底之蛙", "pinyin": "jǐng dǐ zhī wā", "meaning": "persona de visión limitada", "literal": "rana en fondo de pozo", "example": "别做井底之蛙。", "example_tr": "No seas de visión limitada."},
    {"word": "班门弄斧", "pinyin": "bān mén nòng fǔ", "meaning": "presumir ante expertos", "literal": "en puerta de Ban manejar hacha", "example": "在你面前班门弄斧了。", "example_tr": "Presumiendo ante un experto."},
    {"word": "卧薪尝胆", "pinyin": "wò xīn cháng dǎn", "meaning": "perseverar con sacrificio", "literal": "dormir leño probar hiel", "example": "卧薪尝胆终成功。", "example_tr": "Perseverar con sacrificio hasta triunfar."},
    {"word": "破釜沉舟", "pinyin": "pò fǔ chén zhōu", "meaning": "quemar naves, sin retorno", "literal": "romper ollas hundir barcos", "example": "我们破釜沉舟。", "example_tr": "No hay vuelta atrás."},
    {"word": "掩耳盗铃", "pinyin": "yǎn ěr dào líng", "meaning": "autoengañarse", "literal": "tapar oídos robar campana", "example": "这是掩耳盗铃。", "example_tr": "Eso es autoengaño."},
    {"word": "守株待兔", "pinyin": "shǒu zhū dài tù", "meaning": "esperar pasivamente oportunidades", "literal": "vigilar tronco esperar conejo", "example": "不能守株待兔。", "example_tr": "No se puede esperar pasivamente."},
]

# ═══════════════════════════════════════════════════════════════════
# GRAMÁTICA — Patrones sintácticos clave
# ═══════════════════════════════════════════════════════════════════
GRAMMAR_PATTERNS = [
    {"pattern": "把字句 (bǎ)", "structure": "S + 把 + O + V + 补语", "meaning": "oración bǎ — marcar objeto afectado", "example": "我把密码改了。", "example_tr": "Cambié la contraseña.", "note": "Usa 把 cuando el verbo afecta al objeto de manera específica."},
    {"pattern": "被字句 (bèi)", "structure": "S + 被 + (agente) + V + 补语", "meaning": "voz pasiva", "example": "系统被攻击了。", "example_tr": "El sistema fue atacado.", "note": "被 marca al receptor de una acción."},
    {"pattern": "比较句 (比)", "structure": "A + 比 + B + Adj", "meaning": "comparación: A es más que B", "example": "这个比那个更安全。", "example_tr": "Este es más seguro que aquel.", "note": "比 se usa para comparar dos cosas."},
    {"pattern": "既然...就", "structure": "既然 + A，就 + B", "meaning": "ya que A, entonces B", "example": "既然同意了，就开始吧。", "example_tr": "Ya que aceptaste, empecemos.", "note": "Indica que dado A, B es lógico."},
    {"pattern": "不但...而且", "structure": "不但 + A，而且 + B", "meaning": "no solo A, sino también B", "example": "他不但技术好，而且沟通强。", "example_tr": "No solo tiene buena técnica, sino que también comunica bien.", "note": "Concatena dos cualidades/acciones."},
    {"pattern": "无论...都", "structure": "无论 + A，都 + B", "meaning": "no importa A, siempre B", "example": "无论多难，都要完成。", "example_tr": "Por difícil que sea, hay que terminar.", "note": "Indica incondicionalidad."},
    {"pattern": "即使...也", "structure": "即使 + A，也 + B", "meaning": "aunque A, aun así B", "example": "即使失败，也学到东西。", "example_tr": "Aunque fracase, aprendemos algo.", "note": "Concesión hipotética."},
    {"pattern": "一方面...另一方面", "structure": "一方面 A，另一方面 B", "meaning": "por un lado A, por otro B", "example": "一方面要快，另一方面要稳。", "example_tr": "Por un lado rapidez, por otro estabilidad.", "note": "Presenta dos aspectos de algo."},
    {"pattern": "与其...不如", "structure": "与其 + A，不如 + B", "meaning": "más vale B que A", "example": "与其等待，不如行动。", "example_tr": "Mejor actuar que esperar.", "note": "Preferencia entre dos opciones."},
    {"pattern": "连...都/也", "structure": "连 + A + 都/也 + B", "meaning": "incluso A también B", "example": "连专家都觉得难。", "example_tr": "Hasta los expertos lo encuentran difícil.", "note": "Enfatiza que algo es sorprendente."},
    {"pattern": "得字句 (grado)", "structure": "V + 得 + Adv/Adj", "meaning": "grado o resultado de una acción", "example": "他说得很好。", "example_tr": "Habló muy bien.", "note": "得 conecta verbo con complemento de grado."},
    {"pattern": "是...的", "structure": "S + 是 + [info] + 的", "meaning": "énfasis en cuándo/dónde/cómo", "example": "我是昨天到的。", "example_tr": "Llegué ayer.", "note": "Para detalles ya realizados: énfasis en circunstancia, no en la acción."},
]

# ═══════════════════════════════════════════════════════════════════
# CONVERSACIÓN PROFESIONAL
# ═══════════════════════════════════════════════════════════════════
PROFESSIONAL_PHRASES = [
    {"phrase": "请问您贵姓？", "pinyin": "qǐng wèn nín guì xìng?", "meaning": "¿Cómo se llama usted? (formal)", "context": "Presentación formal"},
    {"phrase": "久仰大名", "pinyin": "jiǔ yǎng dà míng", "meaning": "He escuchado mucho sobre usted", "context": "Presentación formal"},
    {"phrase": "请多指教", "pinyin": "qǐng duō zhǐ jiào", "meaning": "Le ruego su guía", "context": "Presentación formal"},
    {"phrase": "我们开始开会吧", "pinyin": "wǒmen kāishǐ kāihuì ba", "meaning": "Empecemos la reunión", "context": "Reunión"},
    {"phrase": "我来汇报一下进度", "pinyin": "wǒ lái huìbào yíxià jìndù", "meaning": "Voy a reportar el progreso", "context": "Reunión"},
    {"phrase": "这个问题值得探讨", "pinyin": "zhè ge wèntí zhídé tàntǎo", "meaning": "Este problema vale la pena explorar", "context": "Reunión"},
    {"phrase": "我有一个建议", "pinyin": "wǒ yǒu yí ge jiànyì", "meaning": "Tengo una sugerencia", "context": "Reunión"},
    {"phrase": "大家有什么意见？", "pinyin": "dàjiā yǒu shénme yìjiàn?", "meaning": "¿Qué opina el equipo?", "context": "Reunión"},
    {"phrase": "我们达成共识了", "pinyin": "wǒmen dáchéng gòngshí le", "meaning": "Hemos llegado a un consenso", "context": "Reunión"},
    {"phrase": "请您签字确认", "pinyin": "qǐng nín qiānzì quèrèn", "meaning": "Por favor firme para confirmar", "context": "Contratos"},
    {"phrase": "请随时联系我", "pinyin": "qǐng suíshí liánxì wǒ", "meaning": "No dude en contactarme", "context": "Cierre"},
    {"phrase": "期待与您合作", "pinyin": "qīdài yǔ nín hézuò", "meaning": "Espero trabajar con usted", "context": "Cierre"},
    {"phrase": "我们会及时跟进", "pinyin": "wǒmen huì jíshí gēnjìn", "meaning": "Haremos seguimiento a tiempo", "context": "Seguimiento"},
    {"phrase": "请提供反馈", "pinyin": "qǐng tígōng fǎnkuì", "meaning": "Por favor dé su feedback", "context": "Revisión"},
    {"phrase": "截止日期是哪天？", "pinyin": "jiézhǐ rìqī shì nǎ tiān?", "meaning": "¿Cuál es la fecha límite?", "context": "Proyectos"},
    {"phrase": "这个方案可行吗？", "pinyin": "zhè ge fāng'àn kěxíng ma?", "meaning": "¿Es viable este plan?", "context": "Evaluación"},
]

# ═══════════════════════════════════════════════════════════════════
# TECH / CYBERSECURITY — Vocabulario especializado
# ═══════════════════════════════════════════════════════════════════
TECH_VOCAB = [
    {"word": "防火墙", "pinyin": "fánghuǒqiáng", "meaning": "firewall", "category": "red", "example": "配置防火墙规则。", "example_tr": "Configurar reglas del firewall."},
    {"word": "加密", "pinyin": "jiāmì", "meaning": "cifrado, encriptación", "category": "crypto", "example": "加密数据传输。", "example_tr": "Cifrar la transmisión de datos."},
    {"word": "解密", "pinyin": "jiěmì", "meaning": "descifrar, desencriptar", "category": "crypto", "example": "解密文件。", "example_tr": "Descifrar el archivo."},
    {"word": "攻击", "pinyin": "gōngjī", "meaning": "ataque", "category": "amenaza", "example": "受到攻击。", "example_tr": "Bajo ataque."},
    {"word": "防御", "pinyin": "fángyù", "meaning": "defensa", "category": "amenaza", "example": "防御机制。", "example_tr": "Mecanismo de defensa."},
    {"word": "服务器", "pinyin": "fúwùqì", "meaning": "servidor", "category": "infra", "example": "服务器宕机了。", "example_tr": "El servidor está caído."},
    {"word": "客户端", "pinyin": "kèhùduān", "meaning": "cliente (software)", "category": "infra", "example": "客户端应用。", "example_tr": "Aplicación cliente."},
    {"word": "端口", "pinyin": "duānkǒu", "meaning": "puerto (red)", "category": "red", "example": "开放端口。", "example_tr": "Puerto abierto."},
    {"word": "协议", "pinyin": "xiéyì", "meaning": "protocolo", "category": "red", "example": "HTTP协议。", "example_tr": "Protocolo HTTP."},
    {"word": "带宽", "pinyin": "dàikuān", "meaning": "ancho de banda", "category": "red", "example": "带宽不足。", "example_tr": "Ancho de banda insuficiente."},
    {"word": "代理", "pinyin": "dàilǐ", "meaning": "proxy, representante", "category": "red", "example": "代理服务器。", "example_tr": "Servidor proxy."},
    {"word": "日志", "pinyin": "rìzhì", "meaning": "log, registro", "category": "ops", "example": "查看日志。", "example_tr": "Revisar los logs."},
    {"word": "备份", "pinyin": "bèifèn", "meaning": "respaldo, backup", "category": "ops", "example": "定期备份。", "example_tr": "Respaldos periódicos."},
    {"word": "恢复", "pinyin": "huīfù", "meaning": "restaurar, recuperar", "category": "ops", "example": "数据恢复。", "example_tr": "Recuperación de datos."},
    {"word": "权限", "pinyin": "quánxiàn", "meaning": "permisos, privilegios", "category": "auth", "example": "提升权限。", "example_tr": "Elevar privilegios."},
    {"word": "身份", "pinyin": "shēnfèn", "meaning": "identidad", "category": "auth", "example": "身份验证。", "example_tr": "Verificación de identidad."},
    {"word": "令牌", "pinyin": "lìngpái", "meaning": "token", "category": "auth", "example": "访问令牌。", "example_tr": "Token de acceso."},
    {"word": "渗透测试", "pinyin": "shèntòu cèshì", "meaning": "prueba de penetración (pentest)", "category": "ataque", "example": "进行渗透测试。", "example_tr": "Realizar pentest."},
    {"word": "社会工程", "pinyin": "shèhuì gōngchéng", "meaning": "ingeniería social", "category": "ataque", "example": "社会工程攻击。", "example_tr": "Ataque de ingeniería social."},
    {"word": "零日漏洞", "pinyin": "língrì lòudòng", "meaning": "vulnerabilidad zero-day", "category": "amenaza", "example": "零日漏洞利用。", "example_tr": "Explotación de zero-day."},
    {"word": "勒索软件", "pinyin": "lèsuǒ ruǎnjiàn", "meaning": "ransomware", "category": "malware", "example": "勒索软件攻击。", "example_tr": "Ataque de ransomware."},
    {"word": "木马", "pinyin": "mùmǎ", "meaning": "troyano (malware)", "category": "malware", "example": "木马程序。", "example_tr": "Programa troyano."},
    {"word": "后门", "pinyin": "hòumén", "meaning": "backdoor, puerta trasera", "category": "amenaza", "example": "留下后门。", "example_tr": "Dejar un backdoor."},
    {"word": "扫描", "pinyin": "sǎomiáo", "meaning": "escaneo, escanear", "category": "recon", "example": "端口扫描。", "example_tr": "Escaneo de puertos."},
    {"word": "指纹识别", "pinyin": "zhǐwén shíbié", "meaning": "fingerprinting", "category": "recon", "example": "系统指纹识别。", "example_tr": "Fingerprinting del sistema."},
    {"word": "蜜罐", "pinyin": "mìguàn", "meaning": "honeypot", "category": "defense", "example": "部署蜜罐。", "example_tr": "Desplegar honeypot."},
    {"word": "沙箱", "pinyin": "shāxiāng", "meaning": "sandbox, aislamiento", "category": "defense", "example": "沙箱环境。", "example_tr": "Entorno sandbox."},
    {"word": "脱壳", "pinyin": "tuō ké", "meaning": "unpacking (malware)", "category": "analysis", "example": "脱壳分析。", "example_tr": "Análisis de unpacking."},
    {"word": "逆向工程", "pinyin": "nìxiàng gōngchéng", "meaning": "ingeniería inversa", "category": "analysis", "example": "逆向工程分析。", "example_tr": "Análisis de ingeniería inversa."},
    {"word": "流量分析", "pinyin": "liúliàng fēnxī", "meaning": "análisis de tráfico", "category": "analysis", "example": "网络流量分析。", "example_tr": "Análisis de tráfico de red."},
]

# ═══════════════════════════════════════════════════════════════════
# MEDIDAS Y CLASIFICADORES (量词)
# ═══════════════════════════════════════════════════════════════════
MEASURE_WORDS = [
    {"word": "个", "pinyin": "ge", "usage": "general (persona, cosa)", "example": "一个人，一个问题"},
    {"word": "只", "pinyin": "zhī", "usage": "animales, objetos individuales", "example": "一只猫，一只手"},
    {"word": "条", "pinyin": "tiáo", "usage": "cosas largas, ríos, noticias", "example": "一条河，一条新闻"},
    {"word": "张", "pinyin": "zhāng", "usage": "cosas planas", "example": "一张纸，一张桌子"},
    {"word": "本", "pinyin": "běn", "usage": "libros, cuadernos", "example": "一本书，一本字典"},
    {"word": "台", "pinyin": "tái", "usage": "máquinas, equipos", "example": "一台电脑，一台服务器"},
    {"word": "份", "pinyin": "fèn", "usage": "documentos, porciones", "example": "一份报告，一份合同"},
    {"word": "种", "pinyin": "zhǒng", "usage": "tipos, clases", "example": "一种方法，一种病毒"},
    {"word": "次", "pinyin": "cì", "usage": "veces, ocurrencias", "example": "一次攻击，一次测试"},
    {"word": "段", "pinyin": "duàn", "usage": "segmentos, párrafos", "example": "一段代码，一段对话"},
    {"word": "道", "pinyin": "dào", "usage": "líneas, puertas, preguntas", "example": "一道门，一道题"},
    {"word": "项", "pinyin": "xiàng", "usage": "ítems, proyectos, políticas", "example": "一项政策，一项任务"},
]

# ═══════════════════════════════════════════════════════════════════
# INTERFAZ — Devuelve lecciones en formato compatible con sol_learning_advanced
# ═══════════════════════════════════════════════════════════════════

def get_advanced_lessons():
    """Devuelve todas las lecciones avanzadas en formato compatible con SIL."""
    return {
        "chino_hsk3": {
            "title": "HSK 3 — Intermedio-bajo",
            "description": "Vocabulario y gramática de nivel intermedio. Para quien ya domina lo básico.",
            "level": "HSK3",
            "vocabulary": HSK3_VOCAB,
            "phrases": [],
        },
        "chino_hsk4": {
            "title": "HSK 4 — Intermedio",
            "description": "Vocabulario profesional y patrones complejos. Nivel de trabajo.",
            "level": "HSK4",
            "vocabulary": HSK4_VOCAB,
            "phrases": [],
        },
        "chino_hsk5": {
            "title": "HSK 5 — Intermedio-alto",
            "description": "Vocabulario técnico y de ciberseguridad. Lectura y expresión avanzada.",
            "level": "HSK5",
            "vocabulary": HSK5_VOCAB,
            "phrases": [],
        },
        "chino_chengyu": {
            "title": "成语 — Modismos de 4 caracteres",
            "description": "Expresiones idiomáticas chinas esenciales para fluidez cultural.",
            "level": "advanced",
            "vocabulary": CHENGYU,
            "phrases": [],
        },
        "chino_gramatica": {
            "title": "语法 — Patrones gramaticales",
            "description": "Estructuras sintácticas clave: bǎ, bèi, comparaciones, concesivas.",
            "level": "advanced",
            "vocabulary": GRAMMAR_PATTERNS,
            "phrases": [],
        },
        "chino_profesional": {
            "title": "商务 — Chino profesional",
            "description": "Frases para reuniones, presentaciones y negociaciones.",
            "level": "advanced",
            "vocabulary": [],
            "phrases": PROFESSIONAL_PHRASES,
        },
        "chino_tech": {
            "title": "技术 — Ciberseguridad y tecnología",
            "description": "Vocabulario especializado: redes, crypto, malware, pentest.",
            "level": "advanced",
            "vocabulary": TECH_VOCAB,
            "phrases": [],
        },
        "chino_量词": {
            "title": "量词 — Clasificadores",
            "description": "Medidas y clasificadores esenciales para precisión gramatical.",
            "level": "intermediate",
            "vocabulary": MEASURE_WORDS,
            "phrases": [],
        },
    }


def list_advanced_levels():
    """Lista los niveles avanzados disponibles."""
    return [
        {"id": "hsk3", "name": "HSK 3 — Intermedio-bajo", "items": len(HSK3_VOCAB)},
        {"id": "hsk4", "name": "HSK 4 — Intermedio", "items": len(HSK4_VOCAB)},
        {"id": "hsk5", "name": "HSK 5 — Intermedio-alto", "items": len(HSK5_VOCAB)},
        {"id": "chengyu", "name": "成语 — Modismos", "items": len(CHENGYU)},
        {"id": "gramatica", "name": "语法 — Gramática", "items": len(GRAMMAR_PATTERNS)},
        {"id": "profesional", "name": "商务 — Profesional", "items": len(PROFESSIONAL_PHRASES)},
        {"id": "tech", "name": "技术 — Ciberseguridad", "items": len(TECH_VOCAB)},
        {"id": "量词", "name": "量词 — Clasificadores", "items": len(MEASURE_WORDS)},
    ]


def get_total_items():
    """Total de items de aprendizaje avanzado."""
    return (len(HSK3_VOCAB) + len(HSK4_VOCAB) + len(HSK5_VOCAB) +
            len(CHENGYU) + len(GRAMMAR_PATTERNS) +
            len(PROFESSIONAL_PHRASES) + len(TECH_VOCAB) + len(MEASURE_WORDS))
