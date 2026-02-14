from llama_index.core.vector_stores import (
    MetadataFilter,
    MetadataFilters,
    FilterOperator,
    FilterCondition,
)

RETRIEVER_FILTERS = {
    "default": MetadataFilters(
        filters=[
            MetadataFilter(key="type", operator=FilterOperator.EQ, value="image_description"),
            MetadataFilter(key="type", operator=FilterOperator.EQ, value="raw_text"),
        ],
        condition=FilterCondition.OR,
    ),
    "archseek": MetadataFilters(
        filters=[
            MetadataFilter(key="type", operator=FilterOperator.EQ, value="archseek"),
        ],
        condition=FilterCondition.OR,
    ),
    "raw_text": MetadataFilters(
        filters=[
            MetadataFilter(key="type", operator=FilterOperator.EQ, value="raw_text"),
        ],
        condition=FilterCondition.OR,
    ),
    "logic": MetadataFilters(
        filters=[
            MetadataFilter(key="type", operator=FilterOperator.EQ, value="strategy"),
            MetadataFilter(key="type", operator=FilterOperator.EQ, value="goal"),
        ],
        condition=FilterCondition.OR,
    ),
    "summary": MetadataFilters(
        filters=[
            MetadataFilter(key="type", operator=FilterOperator.EQ, value="strategy_summary"),
            MetadataFilter(key="type", operator=FilterOperator.EQ, value="goal_summary"),
        ],
        condition=FilterCondition.OR,
    ),
}
