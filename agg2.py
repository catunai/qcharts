from sqlalchemy import case, outerjoin, text, cast, Integer, literal_column, Table, Column, String, func, inspect, union_all

inspector = inspect(engine)

with SessionLocal() as db, SessionLocal_ETL() as etl:
    tst = db.query(Quote).all()
    print("Quotes count:", len(tst))
    for quote in tst:
        print(f"Quote {quote.quote_number}: {quote.business_name} - {quote.transaction_status}")
        break
    print("Done")

    bound_table = select(
        Quote.quote_number,
        func.sum(case((Quote.transaction_status == "Bound", 1), else_=0)).label("bound_count"),
        func.max(Quote.last_entry_date).label("bound_date"),
        func.max(Quote.product).label("product"),
        func.max(Quote.quote_channel).label("quote_channel")
    ).select_from(
        Quote
    ).group_by(Quote.quote_number).subquery()

    outbound_bound = select(
        *Outbound.__table__.c,
        func.coalesce(bound_table.c.bound_count, 0).label("bound_count"),
        bound_table.c.bound_date,
        bound_table.c.product,
        bound_table.c.quote_channel
    ).select_from(
        Outbound
    ).outerjoin(
        bound_table,
        Outbound.quote_number == bound_table.c.quote_number
    ).subquery()

    outbound_non_organic = select(
        outbound_bound,
        func.extract('week', outbound_bound.c.created_at_dtm).label("week_of_year"),
        func.extract('month', outbound_bound.c.created_at_dtm).label("month_of_year"),
        func.extract('year', outbound_bound.c.created_at_dtm).label("year"),
        func.dateadd(
            text('day'), 
            cast(func.datediff(text('day'), text('1900-01-01'), outbound_bound.c.created_at_dtm) / 7, Integer) * 7 + 4, text('1900-01-01')
        ).label("week_end_date"),
        func.dateadd(
            text('day'),
            -1,
            func.dateadd(
                text('month'),
                func.datediff(text('month'), literal_column("'1900-01-01'"), outbound_bound.c.created_at_dtm) + 1,
                literal_column("'1900-01-01'")
            )
        ).label("month_end_date"),
        func.dateadd(
            text('day'),
            -1,
            func.dateadd(
                text('year'),
                func.datediff(text('year'), literal_column("'1900-01-01'"), outbound_bound.c.created_at_dtm) + 1,
                literal_column("'1900-01-01'")
            )
        ).label("year_end_date")

    ).where(
        outbound_bound.c.created_at_dtm <= outbound_bound.c.bound_date
    ).subquery()

    week_stmt = select(
        literal_column("'week'").label("date_type"),
        outbound_non_organic.c.week_end_date.label("date_value"),
        outbound_non_organic.c.product.label("product"),
        outbound_non_organic.c.quote_channel.label("quote_channel"),
        func.sum(
            case((outbound_non_organic.c.result == "Sale - Policy", 1), else_=0)
        ).label("sale_count"),
        func.count(
            outbound_non_organic.c.quote_number
        ).label("quote_count")
    ).select_from(
        outbound_non_organic
    ).group_by(
        outbound_non_organic.c.week_end_date,
        outbound_non_organic.c.product,
        outbound_non_organic.c.quote_channel
    )

    month_stmt = select(
        literal_column("'month'").label("date_type"),
        outbound_non_organic.c.month_end_date.label("date_value"),
        outbound_non_organic.c.product.label("product"),
        outbound_non_organic.c.quote_channel.label("quote_channel"),
        func.sum(
            case((outbound_non_organic.c.result == "Sale - Policy", 1), else_=0)
        ).label("sale_count"),
        func.count(
            outbound_non_organic.c.quote_number
        ).label("quote_count")
    ).select_from(
        outbound_non_organic
    ).group_by(
        outbound_non_organic.c.month_end_date,
        outbound_non_organic.c.product,
        outbound_non_organic.c.quote_channel
    )

    year_stmt = select(
        literal_column("'year'").label("date_type"),
        outbound_non_organic.c.year_end_date.label("date_value"),
        outbound_non_organic.c.product.label("product"),
        outbound_non_organic.c.quote_channel.label("quote_channel"),
        func.sum(
            case((outbound_non_organic.c.result == "Sale - Policy", 1), else_=0)
        ).label("sale_count"),
        func.count(
            outbound_non_organic.c.quote_number
        ).label("quote_count")
    ).select_from(
        outbound_non_organic
    ).group_by(
        outbound_non_organic.c.year_end_date,
        outbound_non_organic.c.product,
        outbound_non_organic.c.quote_channel
    )

    aggregated_stmt = union_all(
        week_stmt,
        month_stmt,
        year_stmt
    ).subquery()

    per_product_stmt = select(
        aggregated_stmt.c.date_type,
        aggregated_stmt.c.date_value,
        aggregated_stmt.c.product,
        aggregated_stmt.c.quote_channel,
        aggregated_stmt.c.sale_count,
        aggregated_stmt.c.quote_count,
    ).select_from(
        aggregated_stmt
    )

    all_product_stmt = select(
        aggregated_stmt.c.date_type,
        aggregated_stmt.c.date_value,
        literal_column("'all'").label("product"),
        aggregated_stmt.c.quote_channel,
        func.sum(aggregated_stmt.c.sale_count).label("sale_count"),
        func.sum(aggregated_stmt.c.quote_count).label("quote_count"),
    ).select_from(
        aggregated_stmt
    ).group_by(
        aggregated_stmt.c.date_type,
        aggregated_stmt.c.date_value,
        aggregated_stmt.c.quote_channel,
    )

    all_quote_channel_stmt = select(
        aggregated_stmt.c.date_type,
        aggregated_stmt.c.date_value,
        aggregated_stmt.c.product,
        literal_column("'all'").label("quote_channel"),
        func.sum(aggregated_stmt.c.sale_count).label("sale_count"),
        func.sum(aggregated_stmt.c.quote_count).label("quote_count"),
    ).select_from(
        aggregated_stmt
    ).group_by(
        aggregated_stmt.c.date_type,
        aggregated_stmt.c.date_value,
        aggregated_stmt.c.product,
    )

    all_totals_stmt = select(
        aggregated_stmt.c.date_type,
        aggregated_stmt.c.date_value,
        literal_column("'all'").label("product"),
        literal_column("'all'").label("quote_channel"),
        func.sum(aggregated_stmt.c.sale_count).label("sale_count"),
        func.sum(aggregated_stmt.c.quote_count).label("quote_count"),
    ).select_from(
        aggregated_stmt
    ).group_by(
        aggregated_stmt.c.date_type,
        aggregated_stmt.c.date_value,
    )

    combined_stmt = union_all(
        per_product_stmt,
        all_product_stmt,
        all_quote_channel_stmt,
        all_totals_stmt
    ).subquery()

    stmt = select(
        combined_stmt.c.date_type,
        combined_stmt.c.date_value,
        combined_stmt.c.product,
        combined_stmt.c.quote_channel,
        combined_stmt.c.sale_count,
        combined_stmt.c.quote_count,
    ).order_by(
        combined_stmt.c.date_type,
        combined_stmt.c.date_value,
        combined_stmt.c.product,
        combined_stmt.c.quote_channel
    )

    # Define the table schema

    repdata_old = Table(
        "repdata",
        metadata,
        Column("date_type", String),
        Column("date_value", String),
        Column("product", String),
        Column("quote_channel", String),
        Column("sale_count", Integer),
        Column("quote_count", Integer),
        extend_existing=True
    )
    repdata_old.drop(bind=engine)

    repdata = Table(
        "repdata",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("date_type", String),
        Column("date_value", String),
        Column("product", String),
        Column("quote_channel", String),
        Column("sale_count", Integer),
        Column("quote_count", Integer),
        extend_existing=True
    )

    if inspector.has_table("repdata"):
        # repdata.drop(bind=engine)
        print("Table repdata exists, deleting all rows...")
        db.execute(repdata.delete())
    else:
        print("Table repdata does not exist, creating it...")
        repdata.create(bind=engine)

    # Execute the statement and insert the results into the table
    result = db.execute(stmt)
    for row in result:
        # print(row)
        db.execute(repdata.insert().values(**row._mapping))

    db.commit()
    print("Results loaded into repdata")

    tst = db.query(repdata).all()
    print("Quotes count:", len(tst))
    for quote in tst:
        print(f"Quote {quote.date_value}: {quote.product} - {quote.quote_channel}")
        break
    print("Done")
