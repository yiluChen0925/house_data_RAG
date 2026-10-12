from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, Index, Integer, Boolean, DECIMAL,UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from datetime import datetime

# SQLAlchemy 2.0+ 正确导入
Base = declarative_base()


# ========== 1. 二手房表（全字段） ==========
class FtxErShou(Base):
    __tablename__ = "ftx_ershou"

    # 1. 自增主键（数据库层面唯一，仅用于标识行，不参与业务唯一判断）
    auto_id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键ID（数据库内部唯一）")

    # 2. 业务唯一三字段（核心：这三个全部相同才判定为重复）
    id = Column(String(64), nullable=True, default=None, comment="房源唯一标识（Redis主键）")
    verification_code = Column(String(64), nullable=True, default=None, comment="房源唯一标识（核验码）")
    crawl_time = Column(DateTime, nullable=False, default=datetime.now, comment="爬取时间（精确到秒）")

    # 3. 基础标识（保持原有逻辑，均设默认值/允许为空）
    city_abbr = Column(String(16), nullable=True, default=None, comment="城市缩写（dg/gz/sz）")
    city_id = Column(Integer, nullable=True, default=None, comment="城市ID（预留）")
    city_name = Column(String(32), nullable=True, default=None, comment="城市名称")
    house_url = Column(String(255), nullable=True, default=None, comment="房源详情页URL")
    error_msg = Column(Text, nullable=True, default=None, comment="错误信息")

    # 4. 核心信息（数值型设默认0，字符串允许为空）
    total_price = Column(DECIMAL(10, 2), nullable=True, default=0.00, comment="总价（万元）")
    house_tags = Column(String(255), nullable=True, default=None, comment="房源标签（|分隔）")
    house_layout = Column(String(32), nullable=True, default=None, comment="户型")
    build_area = Column(DECIMAL(8, 2), nullable=True, default=0.00, comment="建筑面积（㎡）")
    unit_price = Column(DECIMAL(8, 2), nullable=True, default=0.00, comment="单价（元/平米）")
    house_orientation = Column(String(16), nullable=True, default=None, comment="朝向")
    house_floor = Column(String(16), nullable=True, default=None, comment="楼层")
    total_floor = Column(Integer, default=0, comment="楼层备注")
    house_decoration = Column(String(16), nullable=True, default=None, comment="装修情况")
    community_name = Column(String(128), nullable=True, default=None, comment="小区名称")
    house_area = Column(String(32), nullable=True, default=0.00, comment="所属区域")

    # 5. 详细属性（布尔型设默认False，数值型设0）
    build_year = Column(Integer, nullable=True, default=0, comment="建筑年代")
    property_right = Column(String(32), nullable=True, default=None, comment="产权性质")
    house_structure = Column(String(32), nullable=True, default=None, comment="房屋结构")
    mortgage_info = Column(String(128), nullable=True, default=None, comment="抵押信息")
    floor_height = Column(DECIMAL(4, 2), nullable=True, default=0.00, comment="楼层高度（米）")
    last_transaction = Column(DateTime, nullable=True, default=None, comment="上次交易时间")

    # 6. 描述信息（文本型允许为空）
    core_selling_point = Column(Text, nullable=True, default=None, comment="核心卖点")
    owner_mind = Column(Text, nullable=True, default=None, comment="业主心态")
    tax_analysis = Column(Text, nullable=True, default=None, comment="税费分析")
    community_support = Column(Text, nullable=True, default=None, comment="小区配套")
    service_intro = Column(Text, nullable=True, default=None, comment="服务介绍")
    house_type_interpretation = Column(Text, nullable=True, default=None, comment="户型解读")

    # 7. 小区信息（数值型设0，布尔型设False）
    community_avg_price = Column(DECIMAL(8, 2), nullable=True, default=0.00, comment="小区参考均价（元/平米）")
    year_on_year = Column(String(16), nullable=True, default=None, comment="同比去年")
    month_on_month = Column(String(16), nullable=True, default=None, comment="环比上月")
    property_type = Column(String(32), nullable=True, default=None, comment="物业类型")
    property_fee = Column(DECIMAL(6, 2), nullable=True, default=0.00, comment="物业费用（元/㎡·月）")
    property_year = Column(Integer, nullable=True, default=0, comment="产权年限")
    community_build_year = Column(Integer, nullable=True, default=0, comment="小区建筑年代")
    green_rate = Column(DECIMAL(5, 2), nullable=True, default=0.00, comment="绿化率（%）")
    plot_rate = Column(DECIMAL(5, 2), nullable=True, default=0.00, comment="容积率")
    car_flow = Column(Boolean, nullable=True, default=False, comment="人车分流")
    total_buildings = Column(Integer, nullable=True, default=0, comment="总楼栋数")
    total_households = Column(Integer, nullable=True, default=0, comment="总户数")

    # 8. 成交记录+原始数据（文本型允许为空）
    raw_data = Column(Text, nullable=True, default=None, comment="原始数据（JSON）")

    # 9. 核心：3字段复合唯一索引（仅id+verification_code+crawl_time全相同才判定重复）
    __table_args__ = (
        Index("idx_ershou_city", "city_name"),  # 城市索引（查询优化）
        Index("idx_ershou_community", "community_name"),  # 小区索引（查询优化）
        # 业务唯一约束：三个字段全相同才重复
        UniqueConstraint(
            "id", "verification_code", "crawl_time",
            name="uk_ershou_id_vercode_crawl"
        ),
    )

class WubaErShou(Base):
    __tablename__ = "wuba_ershou"  # 保留原表名

    # 核心修改：house_area从Float改为String（因为是区域文本）
    auto_id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID（唯一）")
    id = Column(String(64), nullable=True, default=None, comment="58房源ID（verification_code）")
    verification_code = Column(String(64), nullable=True, default=None, comment="房源唯一标识（核验码）")
    crawl_time = Column(DateTime, nullable=False, default=datetime.now, comment="爬取时间")
    city_abbr = Column(String(8), nullable=True, default=None, comment="城市缩写")
    city_id = Column(Integer, default=0, comment="城市ID")
    city_name = Column(String(32), nullable=True, default=None, comment="城市名称")
    house_url = Column(String(255), nullable=True, default=None, comment="房源URL")
    error_msg = Column(String(255), nullable=True, default=None, comment="错误信息")
    community_name = Column(String(64), nullable=True, default=None, comment="小区名称")
    house_layout = Column(String(32), nullable=True, default=None, comment="户型（layout）")
    house_area = Column(String(32), nullable=True, default=None, comment="所属区域")
    total_price = Column(Float, default=0.0, comment="总价（万）")
    property_right = Column(String(32), nullable=True, default=None, comment="产权性质")
    property_type = Column(String(32), nullable=True, default=None, comment="物业类型")
    property_year = Column(Integer, default=0, comment="产权年限（property_years）")
    community_avg_price = Column(Float, default=0.0, comment="小区均价（元/㎡）")
    total_households = Column(Integer, default=0, comment="小区户数（community_households）")
    property_fee = Column(Float, default=0.0, comment="物业费（元/㎡·月）")
    plot_rate = Column(Float, default=0.0, comment="容积率（plot_ratio）")
    green_rate = Column(Float, default=0.0, comment="绿化率（%）")
    total_floor = Column(Integer, default=0, comment="楼层信息（floor_info）")
    build_area = Column(Float, default=0.0, comment="建筑面积")
    house_decoration = Column(String(16), nullable=True, default=None, comment="装修情况（decoration）")
    house_orientation = Column(String(16), nullable=True, default=None, comment="朝向（direction）")
    build_year = Column(Integer, default=0, comment="建成年份")
    house_tags = Column(String(255), nullable=True, default=None, comment="房源标签（列表转字符串）")
    raw_data = Column(Text, nullable=True, default=None, comment="原始JSON数据")
    region_name = Column(String(32), nullable=True, default=None, comment="区域名称")
    house_code = Column(String(32), nullable=True, default=None, comment="房屋编码")
    certificate_years = Column(Integer, default=0, comment="房本年限")
    only_house = Column(String(8), nullable=True, default=None, comment="是否唯一住房（是/否）")
    district = Column(String(32), nullable=True, default=None, comment="区域")
    block = Column(String(32), nullable=True, default=None, comment="板块")
    community_interpret = Column(Text, nullable=True, default=None, comment="小区解读（JSON字符串）")

    __table_args__ = (
        Index("idx_58_city", "city_name"),
        Index("idx_58_community", "community_name"),
        UniqueConstraint("id", "crawl_time", name="uk_58_ershou_id_crawl"),
    )

class FtxXinFang(Base):
    __tablename__ = "ftx_xinfang"

    # 核心主键：自增ID（数据库内部唯一）+ 业务唯一约束（id+crawl_time）
    auto_id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID（唯一）")
    id = Column(String(64), nullable=True, default=None, comment="楼盘唯一标识（Redis主键）")  # 允许为空+默认None，避免无值报错

    # 以下字段保留原有逻辑，补充默认值/允许为空（核心：crawl_time设默认值+非空）
    loupan_id = Column(String(64), nullable=True, default=None, comment="楼盘ID")
    crawl_time = Column(DateTime, nullable=False, default=datetime.now, comment="爬取时间")  # 必填+默认当前时间，保证唯一索引有效
    city_name = Column(String(32), nullable=True, default=None, comment="城市名称")
    city_id = Column(Integer, nullable=True, default=0, comment="城市ID")  # 数值型设默认0
    city_abbr = Column(String(16), nullable=True, default=None, comment="城市缩写")
    loupan_index_url = Column(String(255), nullable=True, default=None, comment="楼盘首页URL")
    source_url = Column(String(255), nullable=True, default=None, comment="来源URL")
    error_msg = Column(Text, nullable=True, default=None, comment="错误信息")

    # 基础信息（保留字段长度修改，补充默认值/允许为空）
    loupan_name = Column(String(128), nullable=True, default=None, comment="楼盘名称")
    price = Column(DECIMAL(8, 2), nullable=True, default=0.00, comment="列表页价格（元/㎡）")
    total_price_range = Column(String(32), nullable=True, default=None, comment="总价区间")
    address = Column(String(512), nullable=True, default=None, comment="楼盘地址")  # 从255→512
    tel = Column(String(32), nullable=True, default=None, comment="咨询电话")
    property_type = Column(Text, nullable=True, default=None, comment="物业类别")  # 从32→Text
    project_features = Column(Text, nullable=True, default=None, comment="项目特色")  # 从255→Text
    building_type = Column(String(32), nullable=True, default=None, comment="建筑类别")
    decoration_status = Column(Text, nullable=True, default=None, comment="装修状况")  # 从16→Text
    property_right = Column(Text, nullable=True, default=None, comment="产权年限")  # 从32→Text
    developer = Column(String(128), nullable=True, default=None, comment="开发商")
    sale_address = Column(String(255), nullable=True, default=None, comment="售楼地址")
    consult_phone = Column(String(32), nullable=True, default=None, comment="咨询电话")
    main_huxing = Column(String(128), nullable=True, default=None, comment="主力户型")

    # 销售信息（补充默认值/允许为空）
    sale_status = Column(Text, nullable=True, default=None, comment="销售状态")  # 从32→Text
    open_date = Column(DateTime, nullable=True, default=None, comment="开盘时间")
    delivery_date = Column(DateTime, nullable=True, default=None, comment="交房时间")

    # 小区规划（保留长度修改，补充默认值/允许为空）
    cover_area = Column(DECIMAL(10, 2), nullable=True, default=0.00, comment="占地面积（㎡）")
    building_area = Column(DECIMAL(10, 2), nullable=True, default=0.00, comment="建筑面积（㎡）")
    plot_ratio = Column(DECIMAL(5, 2), nullable=True, default=0.00, comment="容积率")
    greening_rate = Column(DECIMAL(5, 2), nullable=True, default=0.00, comment="绿化率（%）")
    building_total = Column(Integer, nullable=True, default=0, comment="楼栋总数")
    household_total = Column(Integer, nullable=True, default=0, comment="总户数")
    property_company = Column(String(512), nullable=True, default=None, comment="物业公司")  # 从128→512
    property_fee = Column(DECIMAL(6, 2), nullable=True, default=0.00, comment="物业费（元/㎡·月）")
    property_fee_desc = Column(Text, nullable=True, default=None, comment="物业费描述")  # 从128→Text
    parking_num = Column(String(32), nullable=True, default=None, comment="停车位数量")
    parking_desc = Column(String(512), nullable=True, default=None, comment="停车位描述")  # 从128→512
    floor_status = Column(Text, nullable=True, default=None, comment="楼层状况")  # 从32→Text
    power_supply = Column(String(32), nullable=True, default=None, comment="供电")
    water_supply = Column(String(32), nullable=True, default=None, comment="供水")

    # 价格&评分（补充默认值/允许为空）
    unit_price = Column(DECIMAL(8, 2), nullable=True, default=0.00, comment="参考单价（元/㎡）")
    price_date = Column(DateTime, nullable=True, default=None, comment="价格记录时间")
    price_avg = Column(DECIMAL(8, 2), nullable=True, default=0.00, comment="均价（元/㎡）")
    price_start = Column(DECIMAL(8, 2), nullable=True, default=0.00, comment="起价（元/㎡）")
    price_desc = Column(Text, nullable=True, default=None, comment="价格描述")
    comment_score = Column(DECIMAL(3, 1), nullable=True, default=0.0, comment="点评评分")
    comment_count = Column(Integer, nullable=True, default=0, comment="点评数量")

    # 户型+报告+原始数据（保留长度修改，补充默认值/允许为空）
    huxing_crawl_time = Column(DateTime, nullable=True, default=None, comment="户型爬取时间")
    huxing_total = Column(Integer, nullable=True, default=0, comment="户型总数")
    huxing_detail = Column(Text, nullable=True, default=None, comment="户型详情")
    report_crawl_time = Column(DateTime, nullable=True, default=None, comment="报告爬取时间")
    report_total_score = Column(DECIMAL(3, 1), nullable=True, default=0.0, comment="报告总评分")
    report_detail = Column(Text, nullable=True, default=None, comment="报告完整文本")
    raw_data = Column(Text(length=4294967295), nullable=True, default=None, comment="原始数据（JSON）")  # 等效LongText

    # 索引：新增 id+crawl_time 复合唯一索引（核心需求）
    __table_args__ = (
        Index("idx_xinfang_city", "city_name"),
        Index("idx_xinfang_loupan", "loupan_name"),
        # 业务唯一约束：仅 id + crawl_time 全相同才判定重复
        UniqueConstraint("id", "crawl_time", name="uk_xinfang_id_crawl"),
    )


# ========== 3. 成交房源表（全字段） ==========
class FtxChengJiao(Base):
    __tablename__ = "ftx_chengjiao"

    # 核心主键：自增ID + 业务唯一约束（id+crawl_time）
    auto_id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID（唯一）")
    id = Column(String(64), nullable=True, default=None, comment="成交房源唯一标识（Redis主键）")  # 允许为空+默认None，避免无值报错

    # 以下字段保留原有逻辑，补充默认值/允许为空（核心：crawl_time设默认值+非空）
    crawl_time = Column(DateTime, nullable=False, default=datetime.now, comment="爬取时间")  # 必填+默认当前时间，保证唯一索引有效
    city_abbr = Column(String(16), nullable=True, default=None, comment="城市缩写")
    city_name = Column(String(32), nullable=True, default=None, comment="城市名称")
    source_url = Column(String(255), nullable=True, default=None, comment="数据来源URL")

    # 基础信息（补充默认值/允许为空）
    community_name = Column(String(128), nullable=True, default=None, comment="小区名称")
    house_layout = Column(String(32), nullable=True, default=None, comment="户型")
    build_area = Column(DECIMAL(8, 2), nullable=True, default=0.00, comment="建筑面积（㎡）")  # 数值型设默认0
    orientation = Column(String(16), nullable=True, default=None, comment="朝向")
    floor_info = Column(String(32), nullable=True, default=None, comment="楼层信息")
    district = Column(String(64), nullable=True, default=None, comment="区域板块")

    # 成交信息（补充默认值/允许为空）
    deal_date = Column(DateTime, nullable=True, default=None, comment="成交日期")
    total_price = Column(DECIMAL(10, 2), nullable=True, default=0.00, comment="成交总价（万元）")  # 数值型设默认0
    unit_price = Column(DECIMAL(8, 2), nullable=True, default=0.00, comment="成交单价（元/㎡）")  # 数值型设默认0

    # 异常+原始数据（补充默认值/允许为空）
    error_msg = Column(Text, nullable=True, default=None, comment="错误信息")
    raw_data = Column(Text, nullable=True, default=None, comment="原始数据（JSON）")

    # 索引：新增 id+crawl_time 复合唯一索引（核心需求），保留原有索引
    __table_args__ = (
        Index("idx_chengjiao_city", "city_name"),
        Index("idx_chengjiao_deal_date", "deal_date"),
        # 业务唯一约束：仅 id + crawl_time 全相同才判定重复
        UniqueConstraint("id", "crawl_time", name="uk_chengjiao_id_crawl"),
    )


# ========== 数据库连接函数 ==========
def get_sync_mysql_engine(config):
    """同步MySQL引擎（本地脚本用）"""
    engine_url = f"mysql+pymysql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['db']}?charset={config['charset']}"
    engine = create_engine(
        engine_url,
        pool_size=20,
        max_overflow=50,
        pool_recycle=3600,
        echo=False
    )
    # 创建所有表（不存在则建）
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session()


# models.py 里的 get_async_mysql_engine 函数（必须这样写）
async def get_async_mysql_engine(config):
    """异步MySQL引擎（Jupyter用）"""
    engine_url = f"mysql+asyncmy://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['db']}?charset={config['charset']}"
    engine = create_async_engine(
        engine_url,
        pool_size=20,
        max_overflow=50,
        pool_recycle=3600,
        echo=False
    )
    # 异步建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 创建工厂类，不创建实例
    AsyncSessionLocal = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    # 返回引擎 + 工厂类（不是实例）
    return engine, AsyncSessionLocal
