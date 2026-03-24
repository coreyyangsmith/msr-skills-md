---
name: osm-map
description: "Free map search via OpenStreetMap (no API key needed). Search nearby POIs, geocode addresses, find restaurants/shops/stores by name or type using Nominatim + Overpass API + Photon. Use when: user asks about nearby places, directions, or location queries and no paid map API key is available."
homepage: https://nominatim.openstreetmap.org
metadata: { "claw": { "emoji": "🗺️", "requires": { "bins": ["curl"] } } }
---

# OpenStreetMap 免费地图搜索 (osm-map)

通过 curl 调用 OpenStreetMap 免费 API 搜索地点、查询 POI、地理编码。**无需任何 API Key。**

## When to Use

✅ **USE this skill when:**

- "附近有什么餐厅/咖啡店/超市？"
- "找一下北京的蜜雪冰城/星巴克"
- "某个地址的坐标是什么？"
- 用户需要搜索地点但没有高德/百度/Google API Key
- 任何地图搜索需求（全球数据，包括中国）

❌ **DON'T use this skill when:**

- 用户明确要求使用高德地图 → 用 amap 技能
- 需要实时路况/导航 → OSM 不提供实时路况
- 需要中国境内精确的门店电话/营业时间 → 高德更全

## 三个免费 API

### 1. Nominatim — 地址搜索 & 地理编码（最常用）

搜索地名、地址、商家名称，返回坐标和详情。

```bash
# 搜索地点（支持中文）
curl -s "https://nominatim.openstreetmap.org/search?q=蜜雪冰城+桂林&format=json&limit=10&addressdetails=1" -H "User-Agent: SenweaverAgent/1.0"

# 搜索特定类型的地点
curl -s "https://nominatim.openstreetmap.org/search?q=restaurant+beijing&format=json&limit=10" -H "User-Agent: SenweaverAgent/1.0"

# 结构化搜索（更精确）
curl -s "https://nominatim.openstreetmap.org/search?street=中山路&city=桂林&country=China&format=json&limit=5" -H "User-Agent: SenweaverAgent/1.0"
```

**返回字段:** `display_name`(名称), `lat`/`lon`(坐标), `address`(地址详情), `type`(类型), `importance`(重要性)

**注意:** 必须包含 `User-Agent` header，否则请求会被拒绝。速率限制: 1次/秒。

### 2. Overpass API — POI 区域搜索（最强大）

按区域、类型、名称搜索 POI（兴趣点），支持复杂查询。

```bash
# 搜索桂林市区 5km 范围内的所有快餐店
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode "data=[out:json][timeout:25];node[amenity=fast_food](around:5000,25.273566,110.290195);out body;>"

# 搜索北京 3km 内名称包含"蜜雪冰城"的店铺
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode "data=[out:json][timeout:25];(node[name~\"蜜雪冰城\"](around:3000,39.9042,116.4074);way[name~\"蜜雪冰城\"](around:3000,39.9042,116.4074););out center body;"

# 搜索某城市所有咖啡店
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode "data=[out:json][timeout:25];area[name=\"桂林市\"]->.a;node[amenity=cafe](area.a);out body 20;"

# 搜索某区域的超市
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode "data=[out:json][timeout:25];node[shop=supermarket](around:2000,25.273566,110.290195);out body;"

# 搜索某区域的药店
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode "data=[out:json][timeout:25];node[amenity=pharmacy](around:2000,25.273566,110.290195);out body;"
```

**常用 OSM 标签（amenity 类型）:**
| 标签 | 含义 |
|------|------|
| `amenity=restaurant` | 餐厅 |
| `amenity=cafe` | 咖啡店 |
| `amenity=fast_food` | 快餐 |
| `amenity=bar` | 酒吧 |
| `amenity=pharmacy` | 药店 |
| `amenity=hospital` | 医院 |
| `amenity=bank` | 银行 |
| `amenity=atm` | ATM |
| `amenity=fuel` | 加油站 |
| `amenity=parking` | 停车场 |
| `amenity=school` | 学校 |
| `amenity=library` | 图书馆 |
| `amenity=cinema` | 电影院 |
| `amenity=theatre` | 剧院 |
| `amenity=post_office` | 邮局 |

**常用 OSM 标签（shop 类型）:**
| 标签 | 含义 |
|------|------|
| `shop=supermarket` | 超市 |
| `shop=convenience` | 便利店 |
| `shop=bakery` | 面包店 |
| `shop=clothes` | 服装店 |
| `shop=electronics` | 电子产品 |
| `shop=mall` | 购物中心 |
| `shop=mobile_phone` | 手机店 |
| `shop=books` | 书店 |

**其他常用标签:**
| 标签 | 含义 |
|------|------|
| `tourism=hotel` | 酒店 |
| `tourism=attraction` | 旅游景点 |
| `leisure=park` | 公园 |
| `leisure=fitness_centre` | 健身房 |

**返回字段:** `tags.name`(名称), `lat`/`lon`(坐标), `tags.addr:street`(街道), `tags.phone`(电话), `tags.opening_hours`(营业时间), `tags.cuisine`(菜系)

### 3. Photon — 快速文本搜索

基于 OSM 数据的快速搜索引擎，支持模糊匹配。

```bash
# 快速搜索（支持中文）
curl -s "https://photon.komoot.io/api/?q=蜜雪冰城+桂林&limit=10&lang=zh"

# 限定搜索范围（经纬度 + 半径）
curl -s "https://photon.komoot.io/api/?q=咖啡&lat=25.273566&lon=110.290195&limit=10&lang=zh"

# 逆地理编码（坐标→地址）
curl -s "https://photon.komoot.io/reverse?lat=25.273566&lon=110.290195&lang=zh"
```

**返回字段:** `properties.name`(名称), `properties.city`(城市), `properties.street`(街道), `geometry.coordinates`([经度,纬度])

## 逆地理编码（坐标→地址）

```bash
# Nominatim 逆编码
curl -s "https://nominatim.openstreetmap.org/reverse?lat=25.273566&lon=110.290195&format=json&zoom=18" -H "User-Agent: SenweaverAgent/1.0"
```

## 常用城市中心坐标

| 城市 | 纬度 | 经度 |
|------|------|------|
| 北京 | 39.9042 | 116.4074 |
| 上海 | 31.2304 | 121.4737 |
| 广州 | 23.1291 | 113.2644 |
| 深圳 | 22.5431 | 114.0579 |
| 杭州 | 30.2741 | 120.1551 |
| 成都 | 30.5728 | 104.0668 |
| 武汉 | 30.5928 | 114.3055 |
| 南京 | 32.0603 | 118.7969 |
| 桂林 | 25.2736 | 110.2902 |
| 西安 | 34.3416 | 108.9398 |
| 长沙 | 28.2282 | 112.9388 |
| 重庆 | 29.5630 | 106.5516 |

## 使用流程

1. **确定用户需求**: 搜索商家名称？按类型搜索？地址查坐标？
2. **确定城市/坐标**: 从用户消息提取城市，查上方坐标表
3. **选择 API**:
   - 搜索具体商家名称 → 先用 Photon 快速搜索，若结果不够用 Overpass 按名称搜
   - 搜索某类型 POI（餐厅、药店等）→ 用 Overpass API + around 查询
   - 地址/地名查坐标 → 用 Nominatim
   - 坐标查地址 → 用 Nominatim reverse 或 Photon reverse
4. **执行 curl**: 使用 exec 工具
5. **解析 JSON**: 提取名称、地址、坐标、电话等
6. **格式化回复**: 列表呈现，包含名称、地址、距离（可计算）

## 注意事项

- Nominatim 速率限制 **1次/秒**，连续请求间加 `sleep 1`
- Overpass API 无硬性速率限制但请勿滥用
- Photon 最快但数据可能不如 Overpass 全
- OSM 中国数据覆盖较好但可能不如高德/百度完整（特别是小商家）
- 所有坐标使用 WGS-84 坐标系（GPS标准，与高德 GCJ-02 略有偏移）
- Windows 下 curl 命令中的双引号可能需要转义
- Overpass 查询中 around 参数格式: `around:半径米,纬度,经度`（注意是纬度在前！）
