import torch
from torch.utils.data import Dataset
from transformers import AutoTokenizer

from preprocess import clean_code, summary_code_cell


class PointwiseDataset(Dataset):
    def __init__(self, df, model_name_or_path, total_max_len, md_max_len, ctx):
        super().__init__()
        self.df = df.reset_index(drop=True)
        self.md_max_len = md_max_len
        self.total_max_len = total_max_len
        self.tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
        self.ctx = ctx

    def __getitem__(self, index):
        row = self.df.iloc[index]
        inputs = self.tokenizer.encode_plus(
            clean_code(row.source),
            None,
            add_special_tokens=True,
            max_length=self.md_max_len,
            return_token_type_ids=True,
            truncation=True,
        )

        # 개별 코드 셀 토큰의 최대 길이를 동적으로 결정
        num_codes = len(self.ctx[str(row.id)]["codes"])
        code_max_len_ = (self.total_max_len - self.md_max_len) // num_codes

        code_inputs = self.tokenizer.batch_encode_plus(
            [clean_code(str(x)) for x in self.ctx[str(row.id)]["codes"]],
            add_special_tokens=False,
            max_length=code_max_len_,
            truncation=True,
        )

        sep_token_id = self.tokenizer.sep_token_id
        pad_token_id = self.tokenizer.pad_token_id

        ids = inputs["input_ids"]
        for x in code_inputs["input_ids"]:
            ids.extend([sep_token_id] + x)
        ids = ids[: self.total_max_len - 1] + [sep_token_id]
        mask = [1] * len(ids)
        if len(ids) != self.total_max_len:
            ids = ids + [pad_token_id] * (self.total_max_len - len(ids))
            mask = mask + [pad_token_id] * (self.total_max_len - len(mask))
        assert len(ids) == self.total_max_len

        ids = torch.LongTensor(ids)
        mask = torch.LongTensor(mask)
        label = torch.FloatTensor([row.pct_rank])

        return ids, mask, label

    def __len__(self):
        return self.df.shape[0]


class PairwiseDataset(Dataset):
    def __init__(
        self,
        samples,
        df,
        model_name_or_path,
        total_max_len=96,
        md_max_len=48,
    ):
        super().__init__()
        self.samples = samples
        unique_ids = [
            f"{n_id}-{cell_id}"
            for n_id, cell_id in zip(df["id"].values, df["cell_id"].values)
        ]
        self.id2src = dict(zip(unique_ids, df["source"].values))
        self.total_max_len = total_max_len
        self.md_max_len = md_max_len
        self.code_max_len = total_max_len - md_max_len
        self.tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)

    def __getitem__(self, index):
        n_id, md_cell_id, code_cell_id, label = self.samples[index]

        md_unique_id = f"{n_id}-{md_cell_id}"
        md_inputs = self.tokenizer.encode_plus(
            clean_code(self.id2src[md_unique_id]),
            None,
            add_special_tokens=False,
            max_length=self.md_max_len,
            return_token_type_ids=True,
            truncation=True,
        )

        code_unique_id = f"{n_id}-{code_cell_id}"
        code_inputs = self.tokenizer.encode_plus(
            clean_code(summary_code_cell(self.id2src[code_unique_id])),
            None,
            add_special_tokens=False,
            max_length=self.code_max_len,
            return_token_type_ids=True,
            truncation=True,
        )

        cls_token_id = self.tokenizer.cls_token_id
        sep_token_id = self.tokenizer.sep_token_id
        pad_token_id = self.tokenizer.pad_token_id

        md_inputs["input_ids"] = md_inputs["input_ids"][: self.md_max_len - 1]
        code_inputs["input_ids"] = code_inputs["input_ids"][: self.code_max_len - 2]

        ids = (
            [cls_token_id]
            + md_inputs["input_ids"]
            + [sep_token_id]
            + code_inputs["input_ids"]
            + [sep_token_id]
        )
        ids = ids[: self.total_max_len]
        mask = [1] * len(ids)
        if len(ids) != self.total_max_len:
            ids = ids + [pad_token_id] * (self.total_max_len - len(ids))
            mask = mask + [pad_token_id] * (self.total_max_len - len(mask))
        assert len(ids) == self.total_max_len

        ids = torch.LongTensor(ids)
        mask = torch.LongTensor(mask)
        label = torch.FloatTensor([label])
        return ids, mask, label

    def __len__(self):
        return len(self.samples)


class CTPairwiseDataset(Dataset):
    def __init__(
        self,
        samples,
        df,
        model_name_or_path,
        total_max_len=96,
        md_max_len=48,
    ):
        super().__init__()
        self.samples = samples
        unique_ids = [
            f"{n_id}-{cell_id}"
            for n_id, cell_id in zip(df["id"].values, df["cell_id"].values)
        ]
        self.id2src = dict(zip(unique_ids, df["source"].values))
        self.total_max_len = total_max_len
        self.md_max_len = md_max_len
        self.code_max_len = total_max_len - md_max_len
        self.tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)

    def __getitem__(self, index):
        n_id, md_cell_id, code_cell_id, label = self.samples[index]

        md_unique_id = f"{n_id}-{md_cell_id}"
        md_inputs = self.tokenizer.encode_plus(
            clean_code(summary_code_cell(self.id2src[md_unique_id])),
            None,
            add_special_tokens=False,
            max_length=self.md_max_len,
            return_token_type_ids=True,
            truncation=True,
        )

        code_unique_id = f"{n_id}-{code_cell_id}"
        code_inputs = self.tokenizer.encode_plus(
            clean_code(summary_code_cell(self.id2src[code_unique_id])),
            None,
            add_special_tokens=False,
            max_length=self.code_max_len,
            return_token_type_ids=True,
            truncation=True,
        )

        cls_token_id = self.tokenizer.cls_token_id
        sep_token_id = self.tokenizer.sep_token_id
        pad_token_id = self.tokenizer.pad_token_id

        md_inputs["input_ids"] = md_inputs["input_ids"][: self.md_max_len - 1]
        code_inputs["input_ids"] = code_inputs["input_ids"][: self.code_max_len - 2]

        ids = (
            [cls_token_id]
            + md_inputs["input_ids"]
            + [sep_token_id]
            + code_inputs["input_ids"]
            + [sep_token_id]
        )
        ids = ids[: self.total_max_len]
        mask = [1] * len(ids)
        if len(ids) != self.total_max_len:
            ids = ids + [pad_token_id] * (self.total_max_len - len(ids))
            mask = mask + [pad_token_id] * (self.total_max_len - len(mask))
        assert len(ids) == self.total_max_len

        ids = torch.LongTensor(ids)
        mask = torch.LongTensor(mask)
        label = torch.FloatTensor([label])
        return ids, mask, label

    def __len__(self):
        return len(self.samples)


class SiameseDataset(Dataset):
    def __init__(
        self,
        samples,
        df,
        model_name_or_path,
        total_max_len=128,
    ):
        super().__init__()
        self.samples = samples
        unique_ids = [
            f"{n_id}-{cell_id}"
            for n_id, cell_id in zip(df["id"].values, df["cell_id"].values)
        ]
        self.id2src = dict(zip(unique_ids, df["source"].values))
        self.total_max_len = total_max_len
        self.tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)

    def __getitem__(self, index):
        n_id, md_cell_id, code_cell_id, label = self.samples[index]

        md_unique_id = f"{n_id}-{md_cell_id}"
        md_inputs = self.tokenizer.encode_plus(
            clean_code(self.id2src[md_unique_id]),
            None,
            add_special_tokens=True,
            max_length=self.total_max_len,
            return_token_type_ids=True,
            truncation=True,
        )
        code_unique_id = f"{n_id}-{code_cell_id}"
        code_inputs = self.tokenizer.encode_plus(
            clean_code(self.id2src[code_unique_id]),
            None,
            add_special_tokens=True,
            max_length=self.total_max_len,
            return_token_type_ids=True,
            truncation=True,
        )

        sep_token_id = self.tokenizer.sep_token_id
        pad_token_id = self.tokenizer.pad_token_id

        md_ids = md_inputs["input_ids"]
        if len(md_ids) >= self.total_max_len:
            md_ids = md_ids[: self.total_max_len - 1] + [sep_token_id]
        md_mask = [1] * len(md_ids)
        if len(md_ids) != self.total_max_len:
            md_ids = md_ids + [pad_token_id] * (self.total_max_len - len(md_ids))
            md_mask = md_mask + [pad_token_id] * (self.total_max_len - len(md_mask))

        code_ids = code_inputs["input_ids"]
        if len(code_ids) >= self.total_max_len:
            code_ids = code_ids[: self.total_max_len - 1] + [sep_token_id]
        code_mask = [1] * len(code_ids)
        if len(code_ids) != self.total_max_len:
            code_ids = code_ids + [pad_token_id] * (self.total_max_len - len(code_ids))
            code_mask = code_mask + [pad_token_id] * (
                self.total_max_len - len(code_mask)
            )

        return (
            torch.LongTensor(md_ids),
            torch.LongTensor(md_mask),
            torch.LongTensor(code_ids),
            torch.LongTensor(code_mask),
            torch.FloatTensor([label]),
        )

    def __len__(self):
        return len(self.samples)


if __name__ == "__main__":
    import json

    import pandas as pd

    from train import generate_pairs_with_label

    if False:
        df = pd.read_csv("./data/valid.csv")
        samples = generate_pairs_with_label(df)
        dataset = PairwiseDataset(samples, df, "microsoft/codebert-base")

    if False:
        df_valid_md = (
            pd.read_csv("./data/valid_md.csv")
            .drop("parent_id", axis=1)
            .dropna()
            .reset_index(drop=True)
        )
        valid_ctx = json.load(open("./data/valid_ctx_40.json"))
        dataset = PointwiseDataset(
            df_valid_md,
            model_name_or_path="microsoft/codebert-base",
            md_max_len=64,
            total_max_len=512,
            ctx=valid_ctx,
        )

    if False:
        df = pd.read_csv("./data/valid.csv")
        samples = generate_pairs_with_label(df)
        dataset = SimPairwiseDataset(samples, df, "microsoft/codebert-base")

    for idx, data in enumerate(dataset):
        print(data)
        if idx > 100:
            break
