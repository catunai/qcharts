from sqlalchemy import case, distinct, text, cast, Integer, literal_column, Table, Column, String, func, inspect, union_all, select, or_, and_
from sqlalchemy.orm import Session


def create_date_aggregation(cte, date_column, date_type_literal):

    return select(
        literal_column(f"'{date_type_literal}'").label("date_type"),
        date_column.label("date_value"),
        cte.c.product.label("product"),
        cte.c.quote_channel.label("quote_channel"),
        func.sum(case((cte.c.result == "Sale - Policy", 1), else_=0)).label("sale_count"),
        func.count(cte.c.quote_number).label("quote_count"),
        func.sum(cte.c.attempt_ind).label("sum_attempts"),
        func.sum(case((cte.c.attempt_no == 1, 1), else_=0)).label("new_leads_given"),
        func.sum(case((cte.c.attempt_no == 1, cte.c.attempt_ind), else_=0)).label("new_leads_contacted"),
        func.sum(case((cte.c.result == "Sale - No recontact", 1), else_=0)).label("leads_no_recontact_needed")
    ).select_from(
        cte
    ).group_by(
        date_column,
        cte.c.product,
        cte.c.quote_channel
    )


def create_attempt_details_aggregation(cte, date_column, date_type_literal):
    """Create aggregations for attempt details (melted format)"""
    
    # Main query - group by result (NULL values become 'None')
    main_query = select(
        literal_column(f"'{date_type_literal}'").label("date_type"),
        date_column.label("date_value"),
        cte.c.product.label("product"),
        cte.c.quote_channel.label("quote_channel"),
        func.coalesce(cte.c.result, 'None').label("series_name"),
        func.count(cte.c.quote_number).label("series_value")
    ).select_from(
        cte
    ).group_by(
        date_column,
        cte.c.product,
        cte.c.quote_channel,
        cte.c.result
    )
    
    # Total series (count all rows)
    total_query = select(
        literal_column(f"'{date_type_literal}'").label("date_type"),
        date_column.label("date_value"),
        cte.c.product.label("product"),
        cte.c.quote_channel.label("quote_channel"),
        literal_column("'Total'").label("series_name"),
        func.count(cte.c.quote_number).label("series_value")
    ).select_from(
        cte
    ).group_by(
        date_column,
        cte.c.product,
        cte.c.quote_channel
    )
    
    return union_all(main_query, total_query)


def add_rollup_level(base_cte, columns_to_group, column_to_rollup, numeric_columns):
    """
    Add an aggregation level by rolling up a specific column to 'All'.
    
    Returns a UNION of the original data and the aggregated data where 
    column_to_rollup is replaced with 'All' and numeric columns are summed.
    
    Args:
        base_cte: The input CTE/subquery to aggregate
        columns_to_group: List of column names to preserve (group by these)
        column_to_rollup: Column name to replace with 'All' 
        numeric_columns: List of column names to sum during aggregation
    
    Returns:
        UNION of base_cte and aggregated version
    """
    # Get column references from the CTE
    base_columns = base_cte.c
    
    # Build the aggregated query
    select_items = []
    
    # Add grouping columns as-is
    for col_name in columns_to_group:
        select_items.append(getattr(base_columns, col_name).label(col_name))
    
    # Add the rollup column as 'All'
    select_items.append(literal_column("'All'").label(column_to_rollup))
    
    # Add summed numeric columns
    for col_name in numeric_columns:
        select_items.append(func.sum(getattr(base_columns, col_name)).label(col_name))
    
    # Create the aggregated statement
    aggregated_stmt = select(*select_items).select_from(base_cte).group_by(*columns_to_group)
    
    # Union with original
    return union_all(
        select(*[getattr(base_columns, col) for col in columns_to_group + [column_to_rollup] + numeric_columns]),
        aggregated_stmt
    ).cte(f'{base_cte.name}_with_{column_to_rollup}_rollup')


def build_repdata_table(db_session, etl_session, engine, metadata, Quote, Outbound):

    inspector = inspect(engine)

    # Aggregate Quote data by quote_number to get bound occurrences
    bound_table = select(
        Quote.quote_number,
        func.sum(case((Quote.transaction_status == "Bound", 1), else_=0)).label("bound_count"),
        func.max(Quote.last_entry_date).label("last_entry_date"), 
        func.max(Quote.product).label("product"),
        func.max(Quote.quote_channel).label("quote_channel")
    ).select_from(
        Quote
    ).group_by(Quote.quote_number).cte('bound_table')

    # Join bound occurrences with Outbound
    outbound_bound = select(
        *Outbound.__table__.c,
        func.coalesce(bound_table.c.bound_count, 0).label("bound_count"),
        bound_table.c.last_entry_date,
        bound_table.c.product,
        bound_table.c.quote_channel
    ).select_from(
        Outbound
    ).outerjoin(
        bound_table,
        Outbound.quote_number == bound_table.c.quote_number
    ).cte('outbound_bound')

    # Date calculations and filtering
    outbound_non_organic = select(
        outbound_bound,
        func.extract('week', outbound_bound.c.created_at_dtm).label("week_of_year"),
        func.extract('month', outbound_bound.c.created_at_dtm).label("month_of_year"),
        func.extract('year', outbound_bound.c.created_at_dtm).label("year"),
        case(
            (or_(
                and_(
                    outbound_bound.c.scheduled_outbound_dt.is_(None),
                    outbound_bound.c.completed_at_dtm.is_(None)
                    ),
                outbound_bound.c.result.is_(None),
                outbound_bound.c.result == "Sale - No recontact"
                ),
            0),
            else_=1
        ).label("attempt_ind"),
        func.dateadd(
            text('day'), 
            cast(func.datediff(text('day'), literal_column("'1900-01-01'"), outbound_bound.c.created_at_dtm) / 7, Integer) * 7 + 4, 
            literal_column("'1900-01-01'")
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
        or_(
            outbound_bound.c.created_at_dtm <= outbound_bound.c.last_entry_date,
            outbound_bound.c.bound_count == 0
        )
    ).cte('outbound_non_organic')

    # Add new lead indicator using row_number
    dfw = select(
        outbound_non_organic,
            func.row_number().over(
                partition_by=outbound_non_organic.c.quote_number,
                order_by=outbound_non_organic.c.assigned_at_dtm
            ).label("attempt_no")
    ).cte('dfw')

    # Create aggregations by week/month/year using helper function
    week_stmt = create_date_aggregation(dfw, dfw.c.week_end_date, 'week')
    month_stmt = create_date_aggregation(dfw, dfw.c.month_end_date, 'month')
    year_stmt = create_date_aggregation(dfw, dfw.c.year_end_date, 'year')

    # Union all time periods - using CTE for efficiency
    aggregated_stmt = union_all(
        week_stmt,
        month_stmt,
        year_stmt
    ).cte('aggregated')

    # Use iterative rollup approach to create all aggregation levels
    # Start with base aggregation (Level 1: product, channel)
    numeric_columns = [
        'sale_count', 
        'quote_count', 
        'sum_attempts',
        'new_leads_given', 
        'new_leads_contacted', 
        'leads_no_recontact_needed'
    ]
    
    # Iteratively add rollup levels
    result_cte = aggregated_stmt
    
    # Add product rollup (creates levels 1 + 2)
    result_cte = add_rollup_level(
        result_cte,
        columns_to_group=['date_type', 'date_value', 'quote_channel'],
        column_to_rollup='product',
        numeric_columns=numeric_columns
    )
    
    # Add channel rollup (creates levels 1 + 2 + 3 + 4)
    result_cte = add_rollup_level(
        result_cte,
        columns_to_group=['date_type', 'date_value', 'product'],
        column_to_rollup='quote_channel',
        numeric_columns=numeric_columns
    )
    
    # Final statement with ordering
    final_stmt = select(result_cte).order_by(
        text('date_type'),
        text('date_value'),
        text('product'),
        text('quote_channel')
    )

    # Reporting table schema (simplified - removed ta_* columns)
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
        Column("sum_attempts", Integer),
        Column("new_leads_given", Integer),
        Column("new_leads_contacted", Integer),
        Column("leads_no_recontact_needed", Integer),
        extend_existing=True
    )

    # Clear the table if it exists
    if inspector.has_table("repdata"):
        # print("Table repdata exists, deleting all rows...")
        db_session.execute(repdata.delete())
        db_session.commit()
    else:
        # print("Table repdata does not exist, creating it...")
        # repdata.create(bind=engine)
        print("Table repdata does not exist, quitting...")
        return 0

    # Bulk insert results
    result = db_session.execute(final_stmt)
    rows_to_insert = [row._mapping for row in result]
    
    if rows_to_insert:
        db_session.execute(repdata.insert(), rows_to_insert)
        db_session.commit()
        print(f"Successfully loaded {len(rows_to_insert)} rows into repdata")
    else:
        print("No rows to insert into repdata")
    
    repdata_count = len(rows_to_insert) if rows_to_insert else 0
    
    # Now build attempt_details table with melted data
    attempt_details_count = build_attempt_details_table(db_session, dfw, metadata, inspector)
    
    return repdata_count, attempt_details_count


def build_attempt_details_table(db_session, dfw_cte, metadata, inspector):
    """Build the attempt_details table with melted attempt type data"""
    
    # Create aggregations for attempt details by week/month/year
    week_attempt_stmt = create_attempt_details_aggregation(dfw_cte, dfw_cte.c.week_end_date, 'week')
    month_attempt_stmt = create_attempt_details_aggregation(dfw_cte, dfw_cte.c.month_end_date, 'month')
    year_attempt_stmt = create_attempt_details_aggregation(dfw_cte, dfw_cte.c.year_end_date, 'year')
    
    # Union all time periods
    attempt_aggregated_stmt = union_all(
        week_attempt_stmt,
        month_attempt_stmt,
        year_attempt_stmt
    ).cte('attempt_aggregated')
    
    # Use iterative rollup approach to create all aggregation levels
    # Note: series_name is NOT rolled up, it's kept in all aggregations
    numeric_columns = ['series_value']
    
    # Iteratively add rollup levels
    result_cte = attempt_aggregated_stmt
    
    # Add product rollup (creates levels 1 + 2)
    result_cte = add_rollup_level(
        result_cte,
        columns_to_group=['date_type', 'date_value', 'quote_channel', 'series_name'],
        column_to_rollup='product',
        numeric_columns=numeric_columns
    )
    
    # Add channel rollup (creates levels 1 + 2 + 3 + 4)
    result_cte = add_rollup_level(
        result_cte,
        columns_to_group=['date_type', 'date_value', 'product', 'series_name'],
        column_to_rollup='quote_channel',
        numeric_columns=numeric_columns
    )
    
    # Final statement with ordering
    attempt_final_stmt = select(result_cte).order_by(
        text('date_type'),
        text('date_value'),
        text('product'),
        text('quote_channel'),
        text('series_name')
    )
    
    # Attempt details table schema
    attempt_details = Table(
        "attempt_details",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("date_type", String),
        Column("date_value", String),
        Column("product", String),
        Column("quote_channel", String),
        Column("series_name", String),
        Column("series_value", Integer),
        extend_existing=True
    )
    
    # Clear the table if it exists
    if inspector.has_table("attempt_details"):
        db_session.execute(attempt_details.delete())
        db_session.commit()
    else:
        print("Table attempt_details does not exist, quitting...")
        return 0
    
    # Bulk insert results
    result = db_session.execute(attempt_final_stmt)
    rows_to_insert = [row._mapping for row in result]
    
    if rows_to_insert:
        db_session.execute(attempt_details.insert(), rows_to_insert)
        db_session.commit()
        print(f"Successfully loaded {len(rows_to_insert)} rows into attempt_details")
    else:
        print("No rows to insert into attempt_details")
    
    return len(rows_to_insert) if rows_to_insert else 0

with SessionLocal() as db, SessionLocal_ETL() as etl:

    repdata_rows, attempt_details_rows = build_repdata_table(db, etl, engine, metadata, Quote, Outbound)
    print(f"Report data created: {repdata_rows} rows in repdata, {attempt_details_rows} rows in attempt_details")
