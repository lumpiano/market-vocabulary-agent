from pydantic import BaseModel, Field, model_validator


class VocabularyTerm(BaseModel):
    term: str = Field(min_length=1)
    plain_english_definition: str = Field(min_length=1)
    everyday_analogy: str = Field(min_length=1)
    market_example: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)


class QuizQuestion(BaseModel):
    question: str = Field(min_length=1)
    choices: list[str] = Field(min_length=2)
    answer: str = Field(min_length=1)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def answer_must_match_choice(self):
        if self.answer not in self.choices:
            raise ValueError("Quiz answer must match one of the choices.")
        return self


class MarketLesson(BaseModel):
    lesson_date: str = Field(min_length=1)
    weekday: str = Field(min_length=1)
    theme: str = Field(min_length=1)
    bloomberg_notes_used: list[str]
    terms: list[VocabularyTerm]
    cause_and_effect_chain: list[str] = Field(min_length=2)
    quiz: QuizQuestion
    five_minute_study_plan: list[str] = Field(min_length=1)
    sources: list[str]
    disclaimer: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_terms(self):
        if len(self.terms) != 5:
            raise ValueError("Each lesson must contain exactly five terms.")

        normalized_terms = [term.term.strip().lower() for term in self.terms]

        if len(normalized_terms) != len(set(normalized_terms)):
            raise ValueError("Duplicate vocabulary terms were detected.")

        return self